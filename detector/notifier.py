import requests
import json
import time
import os

_config = None
_audit_path = "/var/log/detector/audit.log"


def init_notifier(config):
    global _config, _audit_path
    _config = config
    _audit_path = config["log"]["audit_path"]
    os.makedirs(os.path.dirname(_audit_path), exist_ok=True)


def send_slack(config, action, condition, rate, baseline, duration):
    webhook = config["slack"]["webhook_url"]
    message = {
        "text": (
            f"*{action}*\n"
            f"Condition: `{condition}`\n"
            f"Rate: `{rate} req/s`\n"
            f"Baseline: `{baseline:.2f}`\n"
            f"Duration: `{duration}`\n"
            f"Time: `{time.strftime('%Y-%m-%d %H:%M:%S UTC')}`"
        )
    }
    try:
        requests.post(webhook, json=message, timeout=5)
    except Exception as e:
        print(f"Slack error: {e}")


def send_audit_log(action, ip, condition, rate, baseline, duration="-"):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = (
        f"[{ts}] {action} {ip} | "
        f"{condition} | {rate} | {baseline} | {duration}\n"
    )
    try:
        os.makedirs(os.path.dirname(_audit_path), exist_ok=True)
        with open(_audit_path, "a") as f:
            f.write(line)
    except Exception as e:
        print(f"Audit log error: {e}")
