from flask import Flask, render_template, jsonify, request, send_file
import requests, threading, time, logging
from lamn.config import load_agents
import os
import csv
from datetime import datetime
import pandas as pd

# Clear proxy environment variables for this process only
if 'ALL_PROXY' in os.environ:
    print(f"Detected ALL_PROXY: {os.environ['ALL_PROXY']}")
    print("Temporarily clearing proxy settings for LAMN server...")
    
# Create a clean environment for requests
clean_env_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']
original_proxy_vars = {}

for var in clean_env_vars:
    if var in os.environ:
        original_proxy_vars[var] = os.environ[var]
        del os.environ[var]

print("Using direct connections (no proxy) for LAMN")

# --- Setup Flask ---
template_dir = os.path.join(os.path.dirname(__file__), "templates")
app = Flask(__name__, template_folder=template_dir)
app.logger.disabled = True

# Disable unnecessary logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

# --- SOCKS Proxy Configuration ---
SOCKS_HOST = '127.0.0.1'
SOCKS_PORT = 1080  # Your tunnel is on port 1080, not 8080
USE_SOCKS = False  # Temporarily disable SOCKS to test
USE_SSH_FORWARD = False

# --- Setup SOCKS Session ---
def create_session():
    """Create a requests session for direct connections"""
    return requests.Session()

# Session for direct connections
session = create_session()

# Alternative: Global SOCKS setup (uncomment if needed)
def setup_global_socks():
    """Setup global SOCKS proxy for all socket connections"""
    try:
        socks.set_default_proxy(socks.SOCKS5, SOCKS_HOST, SOCKS_PORT)
        socket.socket = socks.socksocket
        print(f"Global SOCKS proxy configured: {SOCKS_HOST}:{SOCKS_PORT}")
    except Exception as e:
        print(f"Failed to setup global SOCKS proxy: {e}")

# Uncomment the next line if you want to use global SOCKS instead of session-based
# setup_global_socks()

# --- Shared data ---
metrics_data = {}
csv_file_path = 'logs/machine_metrics.csv'

def clear_error_data():
    """Clear any cached error data"""
    global metrics_data
    metrics_data = {}
    print("Cleared cached metrics data")

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
        # Check file size and rotate if needed
        rotate_csv_if_needed()
        
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
        
        # Check for disk space warning
        if disk_percent > 95:
            print(f"DISK SPACE WARNING: {hostname} at {disk_percent:.1f}% disk usage!")
        
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
        
        status_msg = f"Logged: {hostname} - CPU:{cpu_percent}% MEM:{memory_percent}% DISK:{disk_percent}%"
        if USE_SOCKS:
            status_msg += " (via SOCKS)"
        print(status_msg)
        
    except Exception as e:
        print(f"Error logging data for {ip}: {e}")

def rotate_csv_if_needed():
    """Rotate CSV file if it exceeds 5MB"""
    try:
        if os.path.exists(csv_file_path):
            file_size = os.path.getsize(csv_file_path)
            size_mb = file_size / (1024 * 1024)
            
            if size_mb > 5:  # 5MB limit
                # Create timestamp for archived file
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                archived_file = f'logs/machine_metrics_{timestamp}.csv'
                
                # Rename current file to archived file
                os.rename(csv_file_path, archived_file)
                print(f"CSV file rotated: {csv_file_path} -> {archived_file} ({size_mb:.1f}MB)")
                
                # Create new CSV file with headers
                setup_csv_logging()
                print(f"New CSV file created: {csv_file_path}")
                
    except Exception as e:
        print(f"Error rotating CSV file: {e}")

def cleanup_old_csv_files(keep_files=5):
    """Keep only the most recent N archived CSV files"""
    try:
        # Get all archived CSV files
        log_files = []
        for filename in os.listdir('logs'):
            if filename.startswith('machine_metrics_') and filename.endswith('.csv'):
                filepath = os.path.join('logs', filename)
                log_files.append((filepath, os.path.getmtime(filepath)))
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: x[1], reverse=True)
        
        # Remove old files if we have more than keep_files
        if len(log_files) > keep_files:
            files_to_remove = log_files[keep_files:]
            for filepath, _ in files_to_remove:
                os.remove(filepath)
                print(f"Removed old CSV file: {filepath}")
                
    except Exception as e:
        print(f"Error cleaning up old CSV files: {e}")

# --- Poll one agent (MODIFIED FOR SOCKS) ---
def poll_agent(ip):
    """Poll a single agent using direct HTTP connection (bypassing proxy)"""
    try:
        url = f"http://{ip}:5000/metrics"
        # Use session that explicitly bypasses proxy
        response = session.get(url, timeout=10)
        response.raise_for_status()
        
        raw_data = response.json()
        metrics_data[ip] = raw_data
        
        # Log to CSV
        log_machine_data(ip, raw_data)
        
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Connection error: {e}"
        metrics_data[ip] = {"error": error_msg}
        print(f"Client {ip} - {error_msg}")
        
    except requests.exceptions.Timeout as e:
        error_msg = f"Timeout error: {e}"
        metrics_data[ip] = {"error": error_msg}
        print(f"Client {ip} - {error_msg}")
        
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        metrics_data[ip] = {"error": error_msg}
        print(f"Client {ip} - {error_msg}")

# --- Test SOCKS connectivity ---
def test_socks_connectivity():
    """Test if SOCKS proxy is working"""
    if not USE_SOCKS:
        print("SOCKS proxy disabled")
        return True
        
    try:
        # Test basic SOCKS connection
        test_sock = socks.socksocket()
        test_sock.set_proxy(socks.SOCKS5, SOCKS_HOST, SOCKS_PORT)
        test_sock.settimeout(5)
        
        # Try to connect to a test endpoint (Google DNS)
        test_sock.connect(("8.8.8.8", 53))
        test_sock.close()
        
        print(f"SOCKS proxy test successful: {SOCKS_HOST}:{SOCKS_PORT}")
        return True
        
    except Exception as e:
        print(f"SOCKS proxy test failed: {e}")
        print(f"  Make sure your SOCKS tunnel is running on {SOCKS_HOST}:{SOCKS_PORT}")
        return False

# --- Main polling loop ---
def polling_loop():
    print("Starting machine monitoring...")
    
    # Clear any old error data
    clear_error_data()
    
    time.sleep(10)  # Initial delay
    
    while True:
        ips = get_agent_ips()
        if not ips:
            print("No agents configured in ~/.agents.json")
            time.sleep(30)
            continue
            
        threads = []
        
        print(f"\nPolling {len(ips)} agents...")
        for ip in ips:
            t = threading.Thread(target=poll_agent, args=(ip,))
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        print(f"Waiting 150 seconds until next poll...")
        time.sleep(150)  # Poll every 150 seconds

# --- Background polling thread ---
threading.Thread(target=polling_loop, daemon=True).start()

# --- Flask Routes (unchanged) ---
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

@app.route('/clear_cache', methods=['POST'])
def clear_cache():
    """Manual endpoint to clear cached data"""
    clear_error_data()
    return jsonify({"status": "Cache cleared"})

@app.route('/force_poll', methods=['POST'])
def force_poll():
    """Force an immediate poll of all agents"""
    ips = get_agent_ips()
    threads = []
    
    for ip in ips:
        t = threading.Thread(target=poll_agent, args=(ip,))
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()
        
    return jsonify({"status": f"Polled {len(ips)} agents", "data": metrics_data})

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
    print("Using direct HTTP connections to all agents")
    
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)

if __name__ == '__main__':
    start()
