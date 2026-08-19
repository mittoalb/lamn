"""Slack alerts for disk-usage thresholds.

Called from server.poll_agent after each successful probe. Fires at most one
message per (host, mountpoint) per `disk_alert_cooldown` seconds.
"""
import json
import logging
import threading
import time
import urllib.request

logger = logging.getLogger("lamn.alerts")

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
            if now - _last_alert.get(key, 0) < cooldown:
                continue
            _last_alert[key] = now

        _post(webhook, settings, host, ip, mp, pct)


def _post(webhook, settings, host, ip, mountpoint, pct):
    payload = {
        "channel": settings.get("slack_channel", "#img"),
        "username": settings.get("slack_username", "lamn"),
        "text": (
            "*Disk Usage Alert* :warning:\n"
            f"• Host: `{host}` (`{ip}`)\n"
            f"• Mount: `{mountpoint}`\n"
            f"• Usage: *{pct}%*"
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
