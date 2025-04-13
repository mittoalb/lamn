from flask import Flask, jsonify, request
import psutil, datetime, subprocess, socket, platform, logging
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_specs():
    """
    Collect additional hardware specifications including OS details.
    """
    # CPU information
    cpu_info = platform.processor() or "Unknown CPU"

    # GPU information - try to get the GPU name using nvidia-smi
    try:
        gpu_output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            universal_newlines=True,
            timeout=2
        ).strip()
        gpu_info = gpu_output if gpu_output else "No GPU"
    except Exception as e:
        logger.error("Error fetching GPU info: " + str(e))
        gpu_info = "No GPU"
    
    # Total RAM (in bytes)
    ram_total = psutil.virtual_memory().total
    
    # Disk specifications: list each disk's device, mount point, and total capacity.
    disks = psutil.disk_partitions()
    disk_specs = []
    for disk in disks:
        try:
            usage = psutil.disk_usage(disk.mountpoint)
            disk_specs.append({
                "device": disk.device,
                "mountpoint": disk.mountpoint,
                "total": usage.total
            })
        except Exception:
            continue
    
    # Network connectivity: list IPv4 addresses per interface.
    nics = psutil.net_if_addrs()
    connectivity = {}
    for iface, addrs in nics.items():
        connectivity[iface] = [addr.address for addr in addrs if addr.family == socket.AF_INET]
    
    # OS information
    os_info = {
         "system": platform.system(),
         "release": platform.release(),
         "version": platform.version(),
         "platform": platform.platform()
    }
    
    return {
        "cpu": cpu_info,
        "gpu": gpu_info,
        "ram": ram_total,
        "disks": disk_specs,
        "connectivity": connectivity,
        "os": os_info
    }

def get_metrics():
    """
    Collect dynamic performance metrics and include extra hardware specs.
    """
    host_name = socket.gethostname()
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_usage = psutil.virtual_memory().percent

    # Disk I/O counters.
    disk_counters = psutil.disk_io_counters()
    disk_read = disk_counters.read_bytes if disk_counters else None
    disk_write = disk_counters.write_bytes if disk_counters else None

    # GPU usage: try to get utilization for NVIDIA GPUs.
    gpu_usage = None
    try:
        gpu_output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            universal_newlines=True,
            timeout=2
        )
        if gpu_output.strip():
            gpu_usage = float(gpu_output.splitlines()[0].strip())
    except Exception as e:
        logger.error("Error getting GPU utilization: " + str(e))
        gpu_usage = None

    metrics = {
        "host": host_name,
        "cpu": cpu_usage,
        "memory": memory_usage,
        "disk_read_bytes": disk_read,
        "disk_write_bytes": disk_write,
        "gpu": gpu_usage,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    metrics["specs"] = get_specs()
    return metrics

@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify(get_metrics())

@app.route('/shutdown', methods=['POST'])
def shutdown():
    logger.info("Shutdown endpoint called")
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Client shutting down...'

def start():
    logger.info("Starting client on port 5000")
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    start()

