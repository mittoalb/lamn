"""
Standalone metrics probe. Executed over SSH by the server (piped via stdin).
Prints a single JSON document to stdout and exits.
No Flask, no long-lived process.
"""
import datetime, json, platform, socket, subprocess, sys

import psutil


def _format_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


def _cpu_model():
    try:
        import cpuinfo
        return cpuinfo.get_cpu_info().get("brand_raw", "Unknown CPU")
    except Exception:
        return platform.processor() or "Unknown CPU"


def _gpu_name():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            universal_newlines=True, timeout=2,
        ).strip()
        return out or "No GPU"
    except Exception:
        return "No GPU"


def _gpu_util():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu",
             "--format=csv,noheader,nounits"],
            universal_newlines=True, timeout=2,
        )
        if out.strip():
            return float(out.splitlines()[0].strip())
    except Exception:
        pass
    return None


def _disks():
    disk_specs, total, used, free = [], 0, 0, 0
    for d in psutil.disk_partitions():
        try:
            u = psutil.disk_usage(d.mountpoint)
        except Exception:
            continue
        disk_specs.append({
            "device": d.device, "mountpoint": d.mountpoint,
            "total": u.total, "used": u.used, "free": u.free,
            "percent_used": u.percent,
        })
        total += u.total
        used += u.used
        free += u.free
    summary = {
        "total_space": total, "total_used": used, "total_free": free,
        "percent_used": round(100 * used / total, 2) if total else None,
        "total_space_human": _format_bytes(total),
        "total_used_human": _format_bytes(used),
        "total_free_human": _format_bytes(free),
    }
    return disk_specs, summary


def _connectivity():
    nics = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    out = {}
    for iface, addrs in nics.items():
        ipv4 = [a.address for a in addrs if a.family == socket.AF_INET]
        speed = None
        if iface in stats:
            s = stats[iface].speed
            speed = s if s and 0 < s < 65535 else None
        out[iface] = {"addresses": ipv4, "speed": speed}
    return out


def collect():
    disk_specs, disk_summary = _disks()
    specs = {
        "cpu": _cpu_model(),
        "gpu": _gpu_name(),
        "ram": psutil.virtual_memory().total,
        "disks": disk_specs,
        "disk_summary": disk_summary,
        "connectivity": _connectivity(),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "platform": platform.platform(),
        },
    }
    return {
        "host": socket.gethostname(),
        "cpu": psutil.cpu_percent(interval=1),
        "memory": psutil.virtual_memory().percent,
        "gpu": _gpu_util(),
        "disk_total": disk_summary.get("total_space_human"),
        "disk_used": disk_summary.get("total_used_human"),
        "disk_free": disk_summary.get("total_free_human"),
        "disk_percent_used": disk_summary.get("percent_used"),
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "specs": specs,
    }


if __name__ == "__main__":
    json.dump(collect(), sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
