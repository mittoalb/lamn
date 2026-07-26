# lamn — LAN Monitoring Tool

A small Flask app that polls a fleet of Linux hosts over SSH and shows their CPU / memory / GPU / disk metrics on a live web dashboard.

No agent daemon runs on the remote hosts. The server SSHes in every `poll_interval` seconds, pipes `probe.py` over stdin, and reads back a JSON snapshot.

---

## Requirements

- Python 3.9+
- Passwordless SSH (key or Kerberos) from the machine running the server to every host in `~/.agents.json`
- On each remote host: Python with `psutil` available in whatever interpreter the probe lands on

---

## Install

```bash
pip install .
# if a broken setuptools plugin blocks it:
pip install --use-pep517 .
```

---

## Configuration

### `~/.agents.json`
List of hosts to poll:

```json
["10.54.102.10", "10.54.113.24", "164.54.102.61"]
```

Managed by the CLI — you don't have to hand-edit.

### `~/.lamn_config.json`
Optional overrides. Any missing key falls back to defaults in [lamn/config.py](lamn/config.py):

```json
{
  "ssh_user": "tomo",
  "conda_env": "python_servers",
  "poll_interval": 15,
  "connect_timeout": 3,
  "remote_python": "python3",
  "ssh_options": [
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ControlMaster=auto",
    "-o", "ControlPath=~/.ssh/lamn-%r@%h:%p",
    "-o", "ControlPersist=60s"
  ]
}
```

| Key | Meaning |
| --- | --- |
| `ssh_user` | Login user for every remote host (defaults to current UNIX user) |
| `conda_env` | If set, the probe runs from `~/miniconda3/envs/<env>/bin/python` (and common variants) on the remote |
| `remote_python` | Fallback interpreter if no conda env is found |
| `remote_python_path` | Absolute path to a remote interpreter, overrides everything above |
| `poll_interval` | Seconds between poll cycles (default 15) |
| `connect_timeout` | Per-SSH connect timeout (default 3) |
| `ssh_options` | Extra `ssh -o` flags. Override this only if you need e.g. a `ProxyCommand` — you replace the defaults, so re-list the ones you want to keep |

The config is re-read on every poll cycle. No restart needed after edits.

---

## Usage

```bash
# start the server (dashboard on http://localhost:8000)
python -m lamn.cli server start

# stop it
python -m lamn.cli server stop

# manage the host list
python -m lamn.cli add 10.54.113.24
python -m lamn.cli remove 10.54.113.24
python -m lamn.cli list

# terminal view of current metrics
python -m lamn.cli terminal

# run the probe locally (debugging)
python -m lamn.cli probe
```

`add` / `remove` take effect on the next poll cycle — the server does not need to restart.

---

## Web UI

- `http://<host>:8000/`         — live dashboard, refreshes every 5s
- `http://<host>:8000/host/<ip>` — per-host detail
- `http://<host>:8000/agents`   — configured host list
- `http://<host>:8000/metrics`  — raw JSON

Status pills:
- **online** — last poll succeeded
- **stale** — poll failed but a previous success is cached
- **offline** — 3+ consecutive failures
- **unknown** — never successfully polled

---

## Troubleshooting

Every host offline with `Permission denied` → the account running the server can't SSH to the fleet. Test by hand:

```bash
ssh -o BatchMode=yes <ssh_user>@<one_host> hostname
```

If it prompts for a password, set up keys (`ssh-keygen`, `ssh-copy-id`) or fix Kerberos.

`Connection closed by UNKNOWN port 65535` → a `ProxyCommand` in `~/.lamn_config.json` or `~/.ssh/config` is failing (usually the SOCKS proxy it points at isn't running). Remove or fix it.
