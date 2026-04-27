import time
import json
import os


def tail_log(path):
    while not os.path.exists(path):
        time.sleep(1)
    with open(path, "r") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.05)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ip = entry.get("source_ip", "")
                if not ip or ip == "-":
                    ip = entry.get("real_ip", "")
                if "," in ip:
                    ip = ip.split(",")[0].strip()
                entry["source_ip"] = ip
                yield entry
            except json.JSONDecodeError:
                continue
