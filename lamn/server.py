from flask import Flask, render_template, jsonify, request, send_file
import requests, threading, time, logging
from lamn.config import load_agents
import os
import csv
from datetime import datetime
import pandas as pd

# --- Setup Flask ---
template_dir = os.path.join(os.path.dirname(__file__), "templates")
app = Flask(__name__, template_folder=template_dir)
app.logger.disabled = True

# Disable unnecessary logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

# --- Shared data ---
metrics_data = {}
csv_file_path = 'logs/machine_metrics.csv'

# --- Setup CSV logging ---
def setup_csv_logging():
    os.makedirs('logs', exist_ok=True)
    
    # Create CSV file with headers if it doesn't exist
    if not os.path.exists(csv_file_path):
        with open(csv_file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'ip', 'hostname', 'cpu_percent', 'memory_percent', 
                'disk_percent', 'gpu_percent', 'total_memory_gb', 'total_disk_gb',
                'cpu_model', 'gpu_model', 'os_info'
            ])

setup_csv_logging()

# --- Get list of agent IPs from config ---
def get_agent_ips():
    return load_agents()

# --- Extract data and write to CSV ---
def log_machine_data(ip, raw_data):
    """Extract key metrics and append to CSV"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        hostname = raw_data.get('host', ip.split('.')[-1])
        
        # Extract basic metrics
        cpu_percent = raw_data.get('cpu', 0)
        memory_percent = raw_data.get('memory', 0)
        gpu_percent = raw_data.get('gpu', 0) if raw_data.get('gpu') is not None else 0
        
        # Extract disk percentage
        disk_percent = 0
        if 'specs' in raw_data and 'disk_summary' in raw_data['specs']:
            disk_percent = raw_data['specs']['disk_summary'].get('percent_used', 0)
        elif 'disk_percent_used' in raw_data:
            disk_percent = raw_data['disk_percent_used']
        
        # Extract system info
        total_memory_gb = 0
        total_disk_gb = 0
        cpu_model = "Unknown"
        gpu_model = "No GPU"
        os_info = "Unknown"
        
        if 'specs' in raw_data:
            specs = raw_data['specs']
            
            # Memory
            if 'ram' in specs:
                total_memory_gb = round(specs['ram'] / (1024**3), 1)
            
            # Disk
            if 'disk_summary' in specs:
                total_disk_gb = round(specs['disk_summary'].get('total_space', 0) / (1024**3), 1)
            
            # CPU
            cpu_model = specs.get('cpu', 'Unknown')
            
            # GPU
            gpu_model = specs.get('gpu', 'No GPU')
            
            # OS
            if 'os' in specs:
                os_info = f"{specs['os'].get('system', '')} {specs['os'].get('release', '')}".strip()
        
        # Write to CSV
        with open(csv_file_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, ip, hostname, cpu_percent, memory_percent,
                disk_percent, gpu_percent, total_memory_gb, total_disk_gb,
                cpu_model, gpu_model, os_info
            ])
        
        print(f"Logged: {hostname} - CPU:{cpu_percent}% MEM:{memory_percent}% DISK:{disk_percent}%")
        
    except Exception as e:
        print(f"Error logging data for {ip}: {e}")

# --- Poll one agent ---
def poll_agent(ip):
    try:
        response = requests.get(f"http://{ip}:5000/metrics", timeout=2)
        raw_data = response.json()
        metrics_data[ip] = raw_data
        
        # Log to CSV
        log_machine_data(ip, raw_data)
        
    except Exception as e:
        metrics_data[ip] = {"error": "Client not running/not reachable"}
        print(f"Client {ip} not reachable: {e}")

# --- Main polling loop ---
def polling_loop():
    print("Starting machine monitoring...")
    time.sleep(10)  # Initial delay
    
    while True:
        ips = get_agent_ips()
        threads = []
        
        for ip in ips:
            t = threading.Thread(target=poll_agent, args=(ip,))
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        time.sleep(30)  # Poll every 30 seconds

# --- Background polling thread ---
threading.Thread(target=polling_loop, daemon=True).start()

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify(metrics_data)

@app.route('/csv_data', methods=['GET'])
def csv_data():
    """Return CSV data as JSON for charts"""
    try:
        # Read CSV file
        df = pd.read_csv(csv_file_path)
        if len(df) > 1000:
            df = df.tail(1000)
            print(f"CSV file has many entries, returning last 1000 rows")
            
        # Debug: Print column names and first few rows
        print("CSV Columns:", df.columns.tolist())
        print("First row:", df.iloc[0].to_dict() if len(df) > 0 else "No data")
        print("Data types:", df.dtypes.to_dict())
        
        # Convert to JSON format for charts
        data = df.to_dict('records')
        return jsonify(data)
        
    except FileNotFoundError:
        return jsonify([])
    except Exception as e:
        print(f"CSV data error: {e}")
        return jsonify({"error": str(e)})

@app.route('/download_csv')
def download_csv():
    """Download the CSV file"""
    try:
        return send_file(csv_file_path, as_attachment=True, download_name='machine_metrics.csv')
    except FileNotFoundError:
        return "CSV file not found", 404

@app.route('/csv_summary')
def csv_summary():
    """Show summary of CSV data"""
    try:
        df = pd.read_csv(csv_file_path)
        
        # Get latest data for each machine
        latest = df.groupby('hostname').tail(1)
        
        summary = {
            'total_entries': len(df),
            'machines': len(df['hostname'].unique()),
            'time_range': {
                'start': df['timestamp'].min(),
                'end': df['timestamp'].max()
            },
            'latest_data': latest[['hostname', 'cpu_percent', 'memory_percent', 'disk_percent', 'gpu_percent']].to_dict('records')
        }
        
        return jsonify(summary)
        
    except FileNotFoundError:
        return jsonify({"error": "No data available"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/plots')
def plots():
    return render_template('plots.html')

@app.route('/hybrid')
def hybrid():
    return render_template('hybrid_plots.html')

@app.route('/shutdown', methods=['POST'])
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Server shutting down...'

# --- Server Entrypoint ---
def start():
    print("Machine data will be logged to: logs/machine_metrics.csv")
    print("View CSV summary at: http://localhost:8000/csv_summary")
    print("Download CSV at: http://localhost:8000/download_csv")
    print("View plots at: http://localhost:8000/plots")
    print("View hybrid dashboard at: http://localhost:8000/hybrid")
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)

if __name__ == '__main__':
    start()
