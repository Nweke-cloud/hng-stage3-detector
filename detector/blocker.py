import subprocess
import threading
import time
from notifier import send_slack, send_audit_log


class Blocker:
    def __init__(self, config):
        self.config = config
        self.banned = {}
        self.ban_counts = {}
        self.lock = threading.Lock()
        self.schedule = [
            m * 60 for m in config["unban"]["schedule_minutes"]
        ]

    def ban(self, ip, condition, rate, baseline):
        with self.lock:
            if ip in self.banned:
                return
            self.banned[ip] = time.time()
            count = self.ban_counts.get(ip, 0)
            self.ban_counts[ip] = count + 1
            duration = self._get_duration(count)
        subprocess.run(
            ["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"],
            capture_output=True
        )
        duration_str = "permanent" if duration < 0 else \
            f"{duration // 60}min"
        send_slack(
            self.config,
            f"BANNED {ip}",
            condition,
            rate,
            baseline,
            duration_str
        )
        send_audit_log(
            "BAN", ip, condition,
            str(rate), str(baseline), duration_str
        )
        if duration > 0:
            t = threading.Timer(duration, self._unban, args=[ip])
            t.daemon = True
            t.start()

    def _unban(self, ip):
        with self.lock:
            if ip not in self.banned:
                return
            del self.banned[ip]
        subprocess.run(
            ["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"],
            capture_output=True
        )
        send_slack(
            self.config,
            f"UNBANNED {ip}",
            "ban_expired",
            0,
            0,
            "-"
        )
        send_audit_log("UNBAN", ip, "ban_expired", "0", "0", "-")

    def _get_duration(self, ban_count):
        if ban_count >= len(self.schedule):
            return -1
        return self.schedule[ban_count]

    def is_banned(self, ip):
        with self.lock:
            return ip in self.banned

    def get_banned(self):
        with self.lock:
            return dict(self.banned)
