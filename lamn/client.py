# lamn/client.py
from flask import Flask, jsonify, request
import psutil, datetime, subprocess, socket, platform, logging, os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_specs():
    """
    Collect additional hardware specifications including detailed CPU model,
    network interface speed (filtered), OS details, and more.
    Includes summary of total disk space usage and free space.
    """
    # CPU: get detailed model using py-cpuinfo if available.
    try:
        import cpuinfo
        cpu_info_full = cpuinfo.get_cpu_info()
        cpu_model = cpu_info_full.get('brand_raw', 'Unknown CPU')
    except ImportError:
        cpu_model = platform.processor() or "Unknown CPU"

    # GPU: try to get the GPU name using nvidia-smi.
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

    # Total RAM in bytes.
    ram_total = psutil.virtual_memory().total

    # Disk specifications: list disks with device, mountpoint, total capacity, and free space.
    disks = psutil.disk_partitions()
    disk_specs = []
    total_space = 0
    total_used = 0
    total_free = 0

    for disk in disks:
        try:
            usage = psutil.disk_usage(disk.mountpoint)
            disk_specs.append({
                "device": disk.device,
                "mountpoint": disk.mountpoint,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent_used": usage.percent
            })
            total_space += usage.total
            total_used += usage.used
            total_free += usage.free
        except Exception:
            continue

    # Convert bytes to human-readable format
    def format_bytes(bytes_val):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.2f} PB"

    # Overall disk usage summary
    disk_summary = {
        "total_space": total_space,
        "total_used": total_used,
        "total_free": total_free,
        "percent_used": round(100 * total_used / total_space, 2) if total_space > 0 else None,
        "total_space_human": format_bytes(total_space),
        "total_used_human": format_bytes(total_used),
        "total_free_human": format_bytes(total_free)
    }

    # Network connectivity: list IPv4 addresses and interface speed.
    nics = psutil.net_if_addrs()
    nic_stats = psutil.net_if_stats()
    connectivity = {}
    for iface, addrs in nics.items():
        ipv4_addresses = [addr.address for addr in addrs if addr.family == socket.AF_INET]
        speed = None
        if iface in nic_stats:
            s = nic_stats[iface].speed
            speed = s if s and s > 0 and s < 65535 else None
        connectivity[iface] = {
            "addresses": ipv4_addresses,
            "speed": speed
        }

    # OS information.
    os_info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "platform": platform.platform()
    }

    return {
        "cpu": cpu_model,
        "gpu": gpu_info,
        "ram": ram_total,
        "disks": disk_specs,
        "disk_summary": disk_summary,
        "connectivity": connectivity,
        "os": os_info
    }


def get_metrics():
    """
    Collect current performance metrics and include extra hardware specs.
    """
    host_name = socket.gethostname()
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_usage = psutil.virtual_memory().percent

    # Disk I/O counters.
    disk_counters = psutil.disk_io_counters()
    disk_read = disk_counters.read_bytes if disk_counters else None
    disk_write = disk_counters.write_bytes if disk_counters else None

    # GPU utilization: try to get the percentage utilization for NVIDIA GPUs.
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

    specs = get_specs()
    disk_summary = specs.get("disk_summary", {})

    metrics = {
        "host": host_name,
        "cpu": cpu_usage,
        "memory": memory_usage,
        "gpu": gpu_usage,
        "disk_total": disk_summary.get("total_space_human"),
        "disk_used": disk_summary.get("total_used_human"),
        "disk_free": disk_summary.get("total_free_human"),
        "disk_percent_used": disk_summary.get("percent_used"),        
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