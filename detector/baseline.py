import time
import threading
from collections import deque
import math


class BaselineTracker:
    def __init__(self, window_minutes=30, recalc_interval=60):
        self.window_minutes = window_minutes
        self.recalc_interval = recalc_interval
        self.per_second_counts = deque()
        self.hourly_slots = {}
        self.effective_mean = 1.0
        self.effective_stddev = 1.0
        self.error_mean = 0.1
        self.error_stddev = 0.1
        self.lock = threading.Lock()
        self.last_recalc = time.time()
        self._start_recalc_thread()

    def _start_recalc_thread(self):
        t = threading.Thread(target=self._recalc_loop, daemon=True)
        t.start()

    def _recalc_loop(self):
        while True:
            time.sleep(self.recalc_interval)
            self.recalculate()

    def add_count(self, count, error_count=0):
        now = time.time()
        with self.lock:
            self.per_second_counts.append((now, count, error_count))
            cutoff = now - (self.window_minutes * 60)
            while self.per_second_counts and \
                    self.per_second_counts[0][0] < cutoff:
                self.per_second_counts.popleft()
            hour_slot = int(now // 3600)
            if hour_slot not in self.hourly_slots:
                self.hourly_slots[hour_slot] = []
            self.hourly_slots[hour_slot].append((count, error_count))
            old_slots = [s for s in self.hourly_slots if s < hour_slot - 2]
            for s in old_slots:
                del self.hourly_slots[s]

    def recalculate(self):
        with self.lock:
            now = time.time()
            current_hour = int(now // 3600)
            current_data = self.hourly_slots.get(current_hour, [])
            if len(current_data) >= 10:
                counts = [c for c, e in current_data]
                errors = [e for c, e in current_data]
            else:
                counts = [c for ts, c, e in self.per_second_counts]
                errors = [e for ts, c, e in self.per_second_counts]
            if len(counts) < 5:
                return
            mean = sum(counts) / len(counts)
            variance = sum((x - mean) ** 2 for x in counts) / len(counts)
            stddev = math.sqrt(variance) if variance > 0 else 0.5
            self.effective_mean = max(mean, 1.0)
            self.effective_stddev = max(stddev, 0.5)
            if errors:
                emean = sum(errors) / len(errors)
                evariance = sum(
                    (x - emean) ** 2 for x in errors
                ) / len(errors)
                self.error_mean = max(emean, 0.1)
                self.error_stddev = max(math.sqrt(evariance), 0.05)
            from notifier import send_audit_log
            send_audit_log(
                "BASELINE_RECALC",
                "-",
                f"mean={self.effective_mean:.2f}",
                f"stddev={self.effective_stddev:.2f}",
                "-"
            )

    def get_baseline(self):
        with self.lock:
            return self.effective_mean, self.effective_stddev

    def get_error_baseline(self):
        with self.lock:
            return self.error_mean, self.error_stddev
