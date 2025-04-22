from flask import Flask, render_template, jsonify, request
import requests, threading, time, logging
from lamn.config import load_agents
import os

# --- Setup logging ---
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- Setup Flask ---
template_dir = os.path.join(os.path.dirname(__file__), "templates")
app = Flask(__name__, template_folder=template_dir)

# --- Shared metrics dictionary ---
metrics_data = {}

# --- Get list of agent IPs from config ---
def get_agent_ips():
    return load_agents()

# --- Poll one agent ---
def poll_agent(ip):
    try:
        response = requests.get(f"http://{ip}:5000/metrics", timeout=2)
        metrics_data[ip] = response.json()
    except Exception as e:
        logger.debug(f"Client {ip} not reachable: {e}")
        metrics_data[ip] = {"error": "Client not running/not reachable"}

# --- Main polling loop ---
def polling_loop():
    logger.info("Waiting 10 seconds before starting agent polling...")
    time.sleep(10)  # Delay at server startup to allow clients to boot

    while True:
        ips = get_agent_ips()
        threads = []

        for ip in ips:
            t = threading.Thread(target=poll_agent, args=(ip,))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        time.sleep(5)  # Poll all agents every 5 seconds

# --- Background polling thread ---
threading.Thread(target=polling_loop, daemon=True).start()

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify(metrics_data)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    logger.info("Shutdown endpoint called")
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'

# --- Server Entrypoint ---
def start():
    logger.info("Starting server on port 8000")
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)

if __name__ == '__main__':
    start()
