import time
import threading
from collections import deque
import math


class AnomalyDetector:
    def __init__(self, config, baseline):
        self.config = config
        self.baseline = baseline
        self.window_seconds = config["detection"]["window_seconds"]
        self.zscore_threshold = config["detection"]["zscore_threshold"]
        self.rate_multiplier = config["detection"]["rate_multiplier_threshold"]
        self.error_multiplier = config["detection"]["error_rate_multiplier"]
        self.ip_windows = {}
        self.global_window = deque()
        self.global_error_window = deque()
        self.lock = threading.Lock()

    def record(self, entry):
        now = time.time()
        ip = entry.get("source_ip", "")
        status = int(entry.get("status", 200))
        is_error = 1 if status >= 400 else 0
        with self.lock:
            if ip not in self.ip_windows:
                self.ip_windows[ip] = deque()
            self.ip_windows[ip].append((now, is_error))
            self._evict(self.ip_windows[ip], now)
            self.global_window.append(now)
            self._evict_ts(self.global_window, now)
            self.global_error_window.append((now, is_error))
            self._evict(self.global_error_window, now)
            old_ips = [
                i for i, w in self.ip_windows.items()
                if not w
            ]
            for i in old_ips:
                del self.ip_windows[i]

    def _evict(self, dq, now):
        cutoff = now - self.window_seconds
        while dq and dq[0][0] < cutoff:
            dq.popleft()

    def _evict_ts(self, dq, now):
        cutoff = now - self.window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()

    def check_ip(self, ip):
        with self.lock:
            window = self.ip_windows.get(ip, deque())
            rate = len(window)
            errors = sum(e for _, e in window)
        mean, stddev = self.baseline.get_baseline()
        emean, estddev = self.baseline.get_error_baseline()
        tightened = errors > self.error_multiplier * emean
        threshold = self.zscore_threshold * 0.7 if tightened else \
            self.zscore_threshold
        multiplier = self.rate_multiplier * 0.7 if tightened else \
            self.rate_multiplier
        if stddev > 0:
            zscore = (rate - mean) / stddev
        else:
            zscore = 0
        if zscore > threshold:
            return True, f"zscore={zscore:.2f}", rate, mean
        if mean > 0 and rate > multiplier * mean:
            return True, f"rate={rate}>{multiplier:.1f}x_mean", rate, mean
        return False, None, rate, mean

    def check_global(self):
        with self.lock:
            rate = len(self.global_window)
        mean, stddev = self.baseline.get_baseline()
        if stddev > 0:
            zscore = (rate - mean) / stddev
        else:
            zscore = 0
        if zscore > self.zscore_threshold:
            return True, f"global_zscore={zscore:.2f}", rate, mean
        if mean > 0 and rate > self.rate_multiplier * mean:
            return True, f"global_rate={rate}", rate, mean
        return False, None, rate, mean

    def get_top_ips(self, n=10):
        with self.lock:
            ip_counts = {
                ip: len(w) for ip, w in self.ip_windows.items() if w
            }
        return sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:n]

    def get_global_rate(self):
        with self.lock:
            return len(self.global_window)
