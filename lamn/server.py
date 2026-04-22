import json
import logging
import os
import shlex
import subprocess
import threading
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, render_template, request

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
    """Build the remote shell command that reads probe.py from stdin.

    Non-interactive SSH shells often skip conda init in ~/.bashrc, so instead
    of `conda activate` we locate the env's python binary directly in the
    common install prefixes. Users can override with remote_python.
    """
    override = settings.get("remote_python_path")
    if override:
        return [override, "-"]

    env = settings.get("conda_env")
    fallback = settings.get("remote_python") or "python3"
    if not env:
        return [fallback, "-"]

    fb_q = shlex.quote(fallback)
    inner = (
        f'for p in '
        f'"$HOME/miniconda3/envs/{env}/bin/python" '
        f'"$HOME/anaconda3/envs/{env}/bin/python" '
        f'"$HOME/miniforge3/envs/{env}/bin/python" '
        f'"$HOME/mambaforge/envs/{env}/bin/python" '
        f'"/opt/conda/envs/{env}/bin/python" '
        f'"/opt/miniconda3/envs/{env}/bin/python"; do '
        f'[ -x "$p" ] && exec "$p" -; done; '
        f'exec {fb_q} -'
    )
    return ["sh", "-c", inner]


def _ssh_argv(ip, settings):
    user = settings["ssh_user"]
    timeout = str(settings["connect_timeout"])
    opts = list(settings.get("ssh_options", []))
    argv = ["ssh", "-o", f"ConnectTimeout={timeout}", *opts, f"{user}@{ip}"]
    argv.extend(_remote_cmd(settings))
    return argv


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
        metrics_data[ip] = {"error": "SSH poll timed out"}
        return
    except Exception as e:
        metrics_data[ip] = {"error": f"SSH failed: {e}"}
        return

    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()[-1:] or ["unknown error"]
        metrics_data[ip] = {"error": f"probe exit {proc.returncode}: {err[0]}"}
        return

    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as e:
        metrics_data[ip] = {"error": f"invalid probe output: {e}"}
        return

    metrics_data[ip] = data

    if ip not in logged_machines:
        specs_logger.info(json.dumps({
            "ip": ip,
            "timestamp": datetime.now().isoformat(),
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
    return render_template('dashboard.html')


@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify(metrics_data)


@app.route('/specs', methods=['GET'])
def specs():
    try:
        with open('logs/machine_specs.log', 'r') as f:
            out = []
            for line in f:
                if not line.strip():
                    continue
                parts = line.strip().split(' ', 2)
                if len(parts) >= 3:
                    rec = json.loads(parts[2])
                    rec['logged_at'] = f"{parts[0]} {parts[1]}"
                    out.append(rec)
            return jsonify(out)
    except FileNotFoundError:
        return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/shutdown', methods=['POST'])
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'


def start():
    print("Complete machine data will be logged to: logs/machine_specs.log")
    print("View specs at: http://localhost:8000/specs")
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)


if __name__ == '__main__':
    start()
