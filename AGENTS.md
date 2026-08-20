# lamn — agent documentation

LAN monitoring tool. Small Flask server polls a fleet of Linux hosts
over SSH every N seconds, pipes a `probe.py` script over stdin, and
collects a JSON snapshot per host (CPU / memory / GPU / disk / uptime).
A live web dashboard at `http://localhost:8000/` shows the fleet.

An AI agent can drive this in three ways — all three coexist:

1. **`lamn` CLI** (existing, human-friendly). Table output via
   `tabulate`. Fine for interactive checks; not ideal for parsing.
2. **`lamn.headless` Python API** (new, agent-friendly). One obvious
   import surface, JSON-native return values.
3. **REST API** on `http://localhost:8000/…` when a server is running.
   `GET /metrics` returns the whole polling snapshot as JSON.

## What lamn is good for from an agent's perspective

- "What's the CPU / memory / GPU load on `tomo2` right now?"
- "Is `hulk` reachable? When was it last polled?"
- "Add `gpu07.aps.anl.gov` to the monitored fleet."
- "List every host we're polling."
- "Run the probe on the local host to verify psutil / SSH / config."

Do NOT use lamn for anything mutation-side on the remote hosts —
lamn is READ-ONLY monitoring. To start/stop services on a host, use
`iocs_monitor` (for IOCs) or `ssh` from `bash` directly.

## Python API — the agent's preferred entry point

```python
from lamn import headless as h

# Fleet config (~/.agents.json)
h.list_agents()                     # ['tomo1', 'tomo2', 'gpu01', ...]
h.add_agent('gpu07.aps.anl.gov')    # writes back to config
h.remove_agent('old-host')

# Live metrics from a running server
h.get_metrics()                     # raw dict {ip: {...}}
h.get_metrics_summary()             # flat list, one row per host,
                                    # pre-digested for reporting

# Run the probe locally (no server needed, no SSH)
h.probe_local()                     # this-host snapshot as dict

# Server lifecycle
h.stop_server()                     # POST /shutdown to local server
h.server_url()                      # 'http://127.0.0.1:8000'
```

`get_metrics_summary()` is the one to prefer when the user asks
"what's on tomo2" — it returns a flat list of dicts with the
common fields, no nested digging:

```python
[
  {
    "ip":           "tomo2.xray.aps.anl.gov",
    "host":         "tomo2",
    "status":       "ok",           # or 'stale', 'unknown', 'error'
    "cpu":          "42.1",
    "memory":       "63.8",
    "gpu":          "13.2",
    "disk_percent": "71%",
    "disk_used":    "3.14 TB",
    "disk_total":   "4.36 TB",
    "last_success": "2026-08-20T15:52:03",
    "last_error":   None,
  },
  ...
]
```

## `lamn` CLI reference

The existing CLI (installed as `lamn`) — human-formatted, but every
subcommand is straightforward to shell out to:

```bash
lamn list                           # print monitored IPs, one per line
lamn add    <ip>                    # append to ~/.agents.json
lamn remove <ip>                    # remove from ~/.agents.json
lamn probe                          # run the local probe, print JSON
lamn server start                   # start the Flask dashboard
lamn server stop                    # POST /shutdown to it
lamn terminal [--url URL]           # print the dashboard as a table
```

`lamn probe` prints JSON directly — safe to `bash: lamn probe | jq …`
from the agent side. `lamn list` prints one IP per line — safe to
grep.

## REST API (when a server is running)

```
GET  http://<host>:8000/metrics     # full polling dict, JSON
POST http://<host>:8000/shutdown    # request graceful stop
GET  http://<host>:8000/            # HTML dashboard (not for agent)
GET  http://<host>:8000/agents      # HTML page (not for agent)
GET  http://<host>:8000/host/<ip>   # HTML per-host page (not for agent)
```

For programmatic use always prefer `/metrics` (JSON), never the HTML
routes.

## Config files

Both are per-user, plain JSON, hand-editable — the agent may need to
`read_file` them to answer "what hosts are we monitoring / how often
does it poll":

- `~/.agents.json` — flat list of IPs / hostnames to poll.
- `~/.lamn_config.json` — settings dict. Keys:
  - `ssh_user`      — SSH user for remote polling (default: current user)
  - `remote_python` — interpreter to run the probe under (default: `python3`)
  - `conda_env`     — optional conda env to activate first
  - `poll_interval` — seconds between polls (default: 15)
  - `connect_timeout` — SSH connect timeout in seconds (default: 3)
  - `ssh_options`   — extra args passed to `ssh` (defaults enable
                      `ControlMaster` for connection reuse)

## Install

```bash
pip install -e /home/beams/AMITTONE/Software/lamn
```

That gets you both the `lamn` CLI and `from lamn import headless`.
The AI agent picks up `lamn` automatically once it's listed in
`~/.pystream/agent_packages.json` — the `AGENTS.md` you're reading
is then copied to `~/.pystream/docs/lamn_AGENTS.md`.

## Common gotchas

- **Passwordless SSH is a hard requirement.** The server SSHes each
  host every `poll_interval` seconds with `BatchMode=yes`. If key
  auth or Kerberos isn't set up, every poll returns "error" until
  it is. The user fixes SSH; lamn just reports what it saw.
- **The probe expects `psutil` in the remote env.** If a host's
  Python doesn't have psutil, the probe fails and status shows
  `error`. Fix by installing psutil on that host or overriding
  `remote_python` / `conda_env` in `~/.lamn_config.json`.
- **`get_metrics()` returns whatever the last poll captured.** A
  stale entry means the server hasn't reached that host recently —
  check `_last_success` and `_last_error` on that entry.
- **Two servers on port 8000 will collide.** If `lamn server start`
  says the port is in use, another lamn (or something else) is
  already there; `stop_server()` targets the running one.
- **`add_agent` / `remove_agent` don't restart the poll loop.** The
  running server picks up the new list on the next `poll_interval`
  boundary — no explicit reload needed.

## Files touched by an agent

- Read: `~/.agents.json`, `~/.lamn_config.json`, `GET /metrics`.
- Write: `~/.agents.json` (only via `add_agent`/`remove_agent`).
- Fire-and-forget: nothing — lamn is read-only monitoring on the
  remote hosts (probe reads system stats, doesn't change them).
