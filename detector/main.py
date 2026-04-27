import threading
import time
import yaml
import os
import ipaddress
from monitor import tail_log
from baseline import BaselineTracker
from detector import AnomalyDetector
from blocker import Blocker
from notifier import init_notifier, send_audit_log, send_slack
from dashboard import init_dashboard, run_dashboard

with open("config.yaml") as f:
    config = yaml.safe_load(f)

# Override webhook from environment variable if set
slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "")
if slack_webhook:
    config["slack"]["webhook_url"] = slack_webhook

init_notifier(config)

baseline = BaselineTracker(
    window_minutes=config["detection"]["baseline_window_minutes"],
    recalc_interval=config["detection"]["baseline_recalc_interval"]
)

detector = AnomalyDetector(config, baseline)
blocker = Blocker(config)

state = {}
state_lock = threading.Lock()

init_dashboard(state, state_lock)

WHITELIST = config["detection"].get("whitelist", [])


def is_whitelisted(ip):
    if not ip:
        return True
    for entry in WHITELIST:
        try:
            if "/" in entry:
                if ipaddress.ip_address(ip) in ipaddress.ip_network(entry):
                    return True
            else:
                if ip == entry:
                    return True
        except ValueError:
            continue
    return False


def update_state():
    while True:
        mean, stddev = baseline.get_baseline()
        with state_lock:
            state["global_rate"] = detector.get_global_rate()
            state["mean"] = mean
            state["stddev"] = stddev
            state["banned"] = blocker.get_banned()
            state["top_ips"] = detector.get_top_ips()
        time.sleep(2)


def process_logs():
    log_path = config["log"]["path"]
    print(f"Starting log monitor: {log_path}", flush=True)
    per_second = 0
    per_second_errors = 0
    last_tick = time.time()

    for entry in tail_log(log_path):
        detector.record(entry)
        ip = entry.get("source_ip", "")
        status = int(entry.get("status", 200))
        per_second += 1
        if status >= 400:
            per_second_errors += 1

        now = time.time()
        if now - last_tick >= 1.0:
            baseline.add_count(per_second, per_second_errors)
            per_second = 0
            per_second_errors = 0
            last_tick = now

        if ip and not blocker.is_banned(ip) and not is_whitelisted(ip):
            anomalous, condition, rate, mean = detector.check_ip(ip)
            if anomalous:
                print(
                    f"[BAN] {ip} condition={condition} "
                    f"rate={rate} mean={mean:.2f}",
                    flush=True
                )
                blocker.ban(ip, condition, rate, mean)

        anomalous, condition, rate, mean = detector.check_global()
        if anomalous:
            print(
                f"[GLOBAL] condition={condition} "
                f"rate={rate} mean={mean:.2f}",
                flush=True
            )
            send_slack(config, "GLOBAL ANOMALY", condition, rate, mean, "-")
            send_audit_log(
                "GLOBAL_ANOMALY", "-", condition,
                str(rate), str(mean)
            )


t1 = threading.Thread(target=process_logs, daemon=True)
t2 = threading.Thread(target=update_state, daemon=True)
t1.start()
t2.start()

port = config["dashboard"]["port"]
print(f"Dashboard running on port {port}", flush=True)
run_dashboard(port)
