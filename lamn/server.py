import json
import logging
import os
import shlex
import subprocess
import threading
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import Flask, abort, jsonify, render_template, request

from lamn.config import load_agents, load_settings

PROBE_PATH = os.path.join(os.path.dirname(__file__), "probe.py")


# --- logging ---------------------------------------------------------------
def setup_logging():
    os.makedirs('logs', exist_ok=True)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)

    specs_logger = logging.getLogger('machine_specs')
    specs_logger.setLevel(logging.INFO)
    specs_logger.propagate = False

    fh = RotatingFileHandler('logs/machine_specs.log',
                             maxBytes=50 * 1024 * 1024, backupCount=3)
    fh.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    specs_logger.addHandler(fh)
    return specs_logger


specs_logger = setup_logging()

# --- Flask -----------------------------------------------------------------
template_dir = os.path.join(os.path.dirname(__file__), "templates")
app = Flask(__name__, template_folder=template_dir)
app.logger.disabled = True

metrics_data = {}
logged_machines = set()


# --- SSH polling -----------------------------------------------------------
def _remote_cmd(settings):
    """Return a single shell-safe string to run on the remote host.

    SSH concatenates extra argv with spaces and runs the result through the
    user's LOGIN shell (often tcsh here). We therefore return one argv element
    that is single-quoted — both bash and csh pass single-quoted text through
    literally, after which `sh -c` handles the real parsing.

    Non-interactive SSH shells often skip conda init, so instead of
    `conda activate` we locate the env's python binary directly.
    """
    override = settings.get("remote_python_path")
    if override:
        return f"exec {shlex.quote(override)} -"

    env = settings.get("conda_env")
    fallback = settings.get("remote_python") or "python3"
    if not env:
        return f"exec {shlex.quote(fallback)} -"

    fb_q = shlex.quote(fallback)
    script = (
        'for p in '
        f'"$HOME/miniconda3/envs/{env}/bin/python" '
        f'"$HOME/anaconda3/envs/{env}/bin/python" '
        f'"$HOME/miniforge3/envs/{env}/bin/python" '
        f'"$HOME/mambaforge/envs/{env}/bin/python" '
        f'"/opt/conda/envs/{env}/bin/python" '
        f'"/opt/miniconda3/envs/{env}/bin/python"; do '
        '[ -x "$p" ] && exec "$p" -; done; '
        f'exec {fb_q} -'
    )
    # Wrap for the login shell: `sh -c '<script>'`. shlex.quote handles any
    # embedded single quotes (there shouldn't be any, but be safe).
    return f"sh -c {shlex.quote(script)}"


def _ssh_argv(ip, settings):
    user = settings["ssh_user"]
    timeout = str(settings["connect_timeout"])
    opts = list(settings.get("ssh_options", []))
    return [
        "ssh", "-o", f"ConnectTimeout={timeout}", *opts,
        f"{user}@{ip}",
        _remote_cmd(settings),
    ]


# How many consecutive failed polls before we flip from "stale" to "offline".
OFFLINE_AFTER = 3


def _record_failure(ip, reason):
    prev = metrics_data.get(ip, {})
    fails = prev.get("_fail_count", 0) + 1
    prev["_fail_count"] = fails
    prev["_last_error"] = reason
    prev["_last_attempt"] = datetime.now().isoformat()
    # Status: unknown if we've never seen it; stale if we had data; offline after N fails.
    if prev.get("_last_success"):
        prev["_status"] = "offline" if fails >= OFFLINE_AFTER else "stale"
    else:
        prev["_status"] = "offline" if fails >= OFFLINE_AFTER else "unknown"
    metrics_data[ip] = prev


def poll_agent(ip, settings, probe_src):
    argv = _ssh_argv(ip, settings)
    try:
        proc = subprocess.run(
            argv,
            input=probe_src,
            capture_output=True,
            text=True,
            timeout=settings["connect_timeout"] + 15,
        )
    except subprocess.TimeoutExpired:
        _record_failure(ip, "SSH poll timed out")
        return
    except Exception as e:
        _record_failure(ip, f"SSH failed: {e}")
        return

    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()[-1:] or ["unknown error"]
        _record_failure(ip, f"probe exit {proc.returncode}: {err[0]}")
        return

    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as e:
        _record_failure(ip, f"invalid probe output: {e}")
        return

    now = datetime.now().isoformat()
    data["_status"] = "online"
    data["_fail_count"] = 0
    data["_last_error"] = None
    data["_last_success"] = now
    data["_last_attempt"] = now
    metrics_data[ip] = data

    if ip not in logged_machines:
        specs_logger.info(json.dumps({
            "ip": ip,
            "timestamp": now,
            "machine_data": data,
        }, separators=(',', ':')))
        logged_machines.add(ip)
        print(f"Logged complete data for machine {ip}")


def polling_loop():
    print("Starting machine monitoring (SSH pull mode)...")
    with open(PROBE_PATH, "r") as f:
        probe_src = f.read()

    while True:
        settings = load_settings()
        ips = load_agents()
        threads = []
        for ip in ips:
            t = threading.Thread(target=poll_agent,
                                 args=(ip, settings, probe_src))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        time.sleep(settings.get("poll_interval", 15))


threading.Thread(target=polling_loop, daemon=True).start()


# --- Flask routes ----------------------------------------------------------
@app.route('/')
def index():
    return render_template('dashboard.html', active='dashboard')


@app.route('/agents')
def agents_page():
    return render_template('agents.html', active='agents', agents=load_agents())


@app.route('/host/<ip>')
def host_page(ip):
    if ip not in load_agents():
        abort(404)
    return render_template('host.html', active='', ip=ip)


@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify(metrics_data)


@app.route('/shutdown', methods=['POST'])
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'


def start():
    print("Dashboard: http://localhost:8000/")
    print("Agents:    http://localhost:8000/agents")
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)


if __name__ == '__main__':
    start()
