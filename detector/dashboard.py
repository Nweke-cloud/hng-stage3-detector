import time
import threading
import psutil
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)
_state = {}
_lock = threading.Lock()

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>HNG Anomaly Detector</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: monospace; background: #0d1117; color: #c9d1d9;
               padding: 20px; }
        h1 { color: #58a6ff; }
        .card { background: #161b22; border: 1px solid #30363d;
                padding: 15px; margin: 10px 0; border-radius: 6px; }
        .metric { font-size: 2em; color: #3fb950; }
        .banned { color: #f85149; }
        .warn { color: #d29922; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left;
                 border-bottom: 1px solid #30363d; }
        th { color: #58a6ff; }
    </style>
    <script>
        async function refresh() {
            const r = await fetch('/api/metrics');
            const d = await r.json();
            document.getElementById('uptime').innerText = d.uptime;
            document.getElementById('global_rate').innerText =
                d.global_rate + ' req/s';
            document.getElementById('mean').innerText =
                d.mean.toFixed(2);
            document.getElementById('stddev').innerText =
                d.stddev.toFixed(2);
            document.getElementById('cpu').innerText = d.cpu + '%';
            document.getElementById('mem').innerText = d.memory + '%';
            document.getElementById('banned_count').innerText =
                d.banned_ips.length;
            let banned = '';
            for (const ip of d.banned_ips) {
                banned += '<tr><td class="banned">' + ip.ip +
                    '</td><td>' + ip.since + '</td></tr>';
            }
            document.getElementById('banned_table').innerHTML = banned;
            let top = '';
            for (const [ip, count] of d.top_ips) {
                top += '<tr><td>' + ip + '</td><td>' + count + '</td></tr>';
            }
            document.getElementById('top_table').innerHTML = top;
        }
        setInterval(refresh, 3000);
        refresh();
    </script>
</head>
<body>
    <h1>HNG Anomaly Detection Engine</h1>
    <div class="card">
        <b>Uptime:</b> <span id="uptime">-</span> |
        <b>Global Rate:</b> <span id="global_rate">-</span> |
        <b>Baseline Mean:</b> <span id="mean">-</span> |
        <b>Stddev:</b> <span id="stddev">-</span> |
        <b>CPU:</b> <span id="cpu">-</span> |
        <b>Memory:</b> <span id="mem">-</span>
    </div>
    <div class="card">
        <h3>Banned IPs (<span id="banned_count">0</span>)</h3>
        <table>
            <tr><th>IP</th><th>Banned Since</th></tr>
            <tbody id="banned_table"></tbody>
        </table>
    </div>
    <div class="card">
        <h3>Top 10 Source IPs</h3>
        <table>
            <tr><th>IP</th><th>Req/60s</th></tr>
            <tbody id="top_table"></tbody>
        </table>
    </div>
</body>
</html>
"""

_start_time = time.time()


def init_dashboard(state, lock):
    global _state, _lock
    _state = state
    _lock = lock


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/metrics")
def metrics():
    with _lock:
        s = dict(_state)
    uptime_secs = int(time.time() - _start_time)
    h, rem = divmod(uptime_secs, 3600)
    m, sec = divmod(rem, 60)
    banned_list = [
        {"ip": ip, "since": time.strftime(
            "%H:%M:%S", time.localtime(ts)
        )}
        for ip, ts in s.get("banned", {}).items()
    ]
    return jsonify({
        "uptime": f"{h}h {m}m {sec}s",
        "global_rate": s.get("global_rate", 0),
        "mean": s.get("mean", 0.0),
        "stddev": s.get("stddev", 0.0),
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "banned_ips": banned_list,
        "top_ips": s.get("top_ips", [])
    })


def run_dashboard(port=5000):
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
