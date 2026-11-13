"""Slack alerts for disk-usage thresholds.

Called from server.poll_agent after each successful probe. Fires at most one
message per (host, mountpoint) per `disk_alert_cooldown` seconds.

When an alert fires, a one-off SSH call runs offenders.py on the host to find
the `disk_alert_top_n` biggest entries under the full mountpoint (path, size,
owner) and includes them in the message. This runs in a background thread so
a slow `du` never stalls the poll loop.
"""
import json
import logging
import os
import subprocess
import threading
import time
import urllib.request

from lamn.remote import ssh_argv

logger = logging.getLogger("lamn.alerts")

OFFENDERS_PATH = os.path.join(os.path.dirname(__file__), "offenders.py")

_last_alert = {}
_lock = threading.Lock()


def maybe_disk_alert(ip, data, settings):
    webhook = settings.get("slack_webhook")
    if not webhook:
        return

    threshold = settings.get("disk_alert_threshold", 90)
    cooldown = settings.get("disk_alert_cooldown", 43200)
    host_filter = settings.get("disk_alert_hosts")

    host = data.get("host") or ip
    if host_filter and not any(sub in host for sub in host_filter):
        return

    disks = (data.get("specs") or {}).get("disks") or []
    now = time.monotonic()

    for d in disks:
        pct = d.get("percent_used")
        mp = d.get("mountpoint")
        if pct is None or mp is None or pct <= threshold:
            continue

        key = (ip, mp)
        with _lock:
            # time.monotonic() starts near boot, so a 0 default would
            # suppress every alert during the first `cooldown` s of uptime.
            last = _last_alert.get(key)
            if last is not None and now - last < cooldown:
                continue
            _last_alert[key] = now

        threading.Thread(
            target=_alert,
            args=(webhook, settings, host, ip, d),
            daemon=True,
        ).start()


def _alert(webhook, settings, host, ip, disk):
    try:
        scan = _scan_offenders(ip, disk["mountpoint"], settings)
    except Exception as e:
        scan = {"error": str(e)}
    _post(webhook, settings, host, ip, disk, scan)


def _scan_offenders(ip, mountpoint, settings):
    """SSH to `ip`, run offenders.py on `mountpoint`, return its JSON dict
    (or None if disabled)."""
    top = int(settings.get("disk_alert_top_n", 5))
    if top <= 0:
        return None
    depth = int(settings.get("disk_alert_scan_depth", 1))
    timeout = int(settings.get("disk_alert_scan_timeout", 600))

    with open(OFFENDERS_PATH, "r") as f:
        src = f.read()
    # repr() of a str is a valid Python literal, so the mountpoint reported
    # by the probe is passed through safely.
    src += "\nmain(%r, %d, %d, %d)\n" % (mountpoint, depth, top, timeout)

    try:
        proc = subprocess.run(
            ssh_argv(ip, settings),
            input=src,
            capture_output=True,
            text=True,
            timeout=timeout + settings.get("connect_timeout", 3) + 30,
        )
    except subprocess.TimeoutExpired:
        return {"error": "offender scan timed out"}

    lines = (proc.stdout or "").strip().splitlines()
    if proc.returncode != 0 or not lines:
        err = (proc.stderr or "").strip().splitlines()[-1:] or ["no output"]
        return {"error": f"offender scan exit {proc.returncode}: {err[0]}"}
    try:
        return json.loads(lines[-1])
    except ValueError as e:
        return {"error": f"invalid offender scan output: {e}"}


def _format_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


def _offenders_text(scan):
    if scan is None:
        return ""
    if scan.get("error"):
        return f"\n_Top offenders unavailable: {scan['error']}_"
    offenders = scan.get("offenders") or []
    if not offenders:
        why = " (du could not read the mount)" if scan.get("unreadable") else ""
        return f"\n_Top offenders: none found{why}_"

    lines = [f"\n*Top {len(offenders)} offenders:*"]
    for i, o in enumerate(offenders, 1):
        lines.append(
            f"{i}. `{o['path']}` — *{_format_bytes(o['size'])}* — owner `{o['owner']}`"
        )
    if scan.get("partial"):
        lines.append("_Scan timed out: list is partial._")
    if scan.get("unreadable"):
        lines.append("_Some directories were unreadable: sizes may be under-counted._")
    return "\n".join(lines)


def _post(webhook, settings, host, ip, disk, scan):
    mountpoint = disk["mountpoint"]
    usage = f"*{disk['percent_used']}%*"
    if disk.get("used") is not None and disk.get("total"):
        usage += f" ({_format_bytes(disk['used'])} of {_format_bytes(disk['total'])})"
    payload = {
        "channel": settings.get("slack_channel", "#img"),
        "username": settings.get("slack_username", "lamn"),
        "text": (
            "*Disk Usage Alert* :warning:\n"
            f"• Host: `{host}` (`{ip}`)\n"
            f"• Mount: `{mountpoint}`\n"
            f"• Usage: {usage}"
            + _offenders_text(scan)
        ),
    }
    req = urllib.request.Request(
        webhook,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode(),
    )
    try:
        urllib.request.urlopen(req, timeout=5).close()
    except Exception as e:
        logger.warning("Slack alert failed for %s %s: %s", host, mountpoint, e)
