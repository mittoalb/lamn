"""Headless (non-Flask) API surface for lamn.

The existing `lamn` CLI (`lamn/cli.py`) and Flask server
(`lamn/server.py`) are unchanged. This module gives an AI agent (or
any script) one obvious import to reach every operation without
scraping human-formatted CLI output.

    from lamn import headless as h

    h.list_agents()                     # from ~/.agents.json
    h.add_agent("gpu01.aps.anl.gov")    # writes back to config
    h.remove_agent("old-host")
    h.probe_local()                     # run the probe on THIS host
    h.get_metrics()                     # fetch dashboard state from a
                                        # running lamn server (default
                                        # http://127.0.0.1:8000/metrics)
    h.stop_server()                     # ask the local server to exit
    h.server_url()                      # default server URL constant
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from lamn.config import (
    CONFIG_PATH,
    SETTINGS_PATH,
    add_agent,
    load_agents,
    load_settings,
    remove_agent,
    save_agents,
)
from lamn.probe import collect as _probe_collect


# Default location of a running lamn server on the local host.
# Override via the `url=` arg on any function below when the server
# runs elsewhere (a remote GPU node polling a fleet, etc.).
DEFAULT_SERVER_URL = "http://127.0.0.1:8000"


def server_url() -> str:
    """Return the default server URL. Kept as a function (not a bare
    constant) so callers who monkey-patch the URL for tests hit a
    single seam."""
    return DEFAULT_SERVER_URL


# ── agent list (persistent config) ──────────────────────────────────

def list_agents() -> List[str]:
    """Return the current list of monitored hosts from
    `~/.agents.json`. Empty list if the file doesn't exist."""
    return list(load_agents())


# `add_agent` / `remove_agent` re-exported from lamn.config above —
# they modify `~/.agents.json` in place. Both return True on change,
# False if the change was a no-op.


# ── local probe (no server needed) ──────────────────────────────────

def probe_local() -> Dict[str, Any]:
    """Run the probe on THIS host and return the JSON snapshot the
    server would collect via SSH. Useful for debugging a host's
    metrics without deploying it into the fleet, or as a sanity
    check that `psutil` is available in this env."""
    return _probe_collect()


# ── live metrics from a running server ──────────────────────────────

def get_metrics(url: Optional[str] = None,
                timeout: float = 5.0) -> Dict[str, Any]:
    """Fetch the dashboard's current metrics dict from a running lamn
    server. Returns the raw JSON `metrics_data` — a dict keyed by IP,
    each value a probe snapshot plus `_last_success` / `_last_error` /
    `_status` metadata added by the polling loop.

    `url` defaults to `http://127.0.0.1:8000/metrics`. Raises the
    usual `requests` exceptions if the server isn't reachable — the
    caller is expected to catch and report."""
    base = (url or server_url()).rstrip("/")
    if not base.endswith("/metrics"):
        base = base + "/metrics"
    r = requests.get(base, timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_metrics_summary(url: Optional[str] = None,
                        timeout: float = 5.0) -> List[Dict[str, Any]]:
    """Same as `get_metrics` but pre-digested: one flat row per host
    with the common fields the agent usually wants
    (`ip, host, status, cpu, memory, gpu, disk_percent,
    last_success, last_error`). Missing fields default to None."""
    raw = get_metrics(url=url, timeout=timeout)
    rows = []
    for ip, data in raw.items():
        specs = data.get("specs") or {}
        disk = specs.get("disk_summary") or {}
        rows.append({
            "ip":            ip,
            "host":          data.get("host"),
            "status":        (data.get("_status")
                              or ("stale" if data.get("_last_success")
                                  else "unknown")),
            "cpu":           data.get("cpu"),
            "memory":        data.get("memory"),
            "gpu":           data.get("gpu"),
            "disk_percent":  disk.get("percent_used"),
            "disk_used":     disk.get("total_used_human"),
            "disk_total":    disk.get("total_space_human"),
            "last_success":  data.get("_last_success"),
            "last_error":    data.get("_last_error"),
        })
    return rows


# ── server lifecycle ────────────────────────────────────────────────

def stop_server(url: Optional[str] = None,
                timeout: float = 5.0) -> Dict[str, Any]:
    """Ask a running lamn server to shut down (POST to /shutdown).
    Returns `{"ok": True, "text": <response body>}` on success or
    `{"error": <message>}` on failure. Convenience for scripting a
    controlled restart."""
    base = (url or server_url()).rstrip("/")
    try:
        r = requests.post(f"{base}/shutdown", timeout=timeout)
        r.raise_for_status()
        return {"ok": True, "text": r.text}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


__all__ = [
    # constants + paths
    "CONFIG_PATH", "SETTINGS_PATH", "DEFAULT_SERVER_URL",
    # helpers
    "server_url", "load_settings",
    # agent list
    "list_agents", "add_agent", "remove_agent", "save_agents",
    # metrics
    "probe_local", "get_metrics", "get_metrics_summary",
    # lifecycle
    "stop_server",
]
