# lamn/server.py
from flask import Flask, render_template, jsonify, request
import requests, threading, time, logging
from lamn.config import load_agents

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create the Flask app and specify the templates folder.
app = Flask(__name__, template_folder="templates")

def get_agent_ips():
    return load_agents()

# Global dictionary to store the latest metrics from agents.
metrics_data = {}

def poll_agent(ip):
    try:
        response = requests.get(f'http://{ip}:5000/metrics', timeout=2)
        metrics_data[ip] = response.json()
        logger.debug(f"Polled {ip} successfully")
    except Exception as e:
        metrics_data[ip] = {"error": str(e)}
        logger.error(f"Error polling {ip}: {e}")

def polling_loop():
    while True:
        ips = get_agent_ips()
        threads = []
        for ip in ips:
            t = threading.Thread(target=poll_agent, args=(ip,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        time.sleep(5)  # Poll every 5 seconds

# Start the polling loop in a background thread.
threading.Thread(target=polling_loop, daemon=True).start()

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify(metrics_data)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    logger.info("Server shutdown endpoint called")
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'

def start():
    logger.info("Starting server on port 8000")
    app.run(host='0.0.0.0', port=8000)

