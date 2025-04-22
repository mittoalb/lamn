# lamn-client-launcher

A minimal command-line tool to launch `lamn` clients on multiple remote agents via SSH using `screen` and `conda`. Configuration is handled via JSON files in your home directory.

---

## Features

- Launches `lamn` clients remotely via `ssh`
- Uses `screen` to ensure background execution
- Reads global configuration from `~/.lamn_config.json`
- Loads agent IPs from `~/.agents.json`
- Automatically creates config files if missing
- Validates required config fields on startup

---

## Configuration

### `~/.lamn_config.json` (required)

Stores global defaults used for all agents:

```json
{
  "conda_env": "python_servers",
  "screen_name": "lamn_client",
  "launch_cmd": "python ~/Software/lamn/lamn/cli.py client start"
}
```

If this file does not exist, it will be auto-created as an empty `{}` and the script will exit with an instruction to edit it.

### `~/.agents.json`

A list of IPs to connect to. The SSH username is passed as an argument to the script:

```json
[
  "192.168.1.100",
  "192.168.1.101"
]
```

---

## Usage

```bash
python start_clients.py --username <ssh_username>
```

This will:

- Read the config from `~/.lamn_config.json`
- Load agent IPs from `~/.agents.json`
- SSH into each machine and:
  - Check if a `screen` session with the given name is already running
  - If not, activate the conda environment and start the client in a new screen

---

## Requirements

- Python 3.6+
- `ssh` access to each remote host
- `screen` installed on each remote host
- `conda` installed and properly configured via `.bashrc` on each host

---

## 📎 Example Output

```
[+] Connecting to 192.168.1.100 to start client...
[!] Client already running on 192.168.1.100 (screen lamn_client)

[+] Connecting to 192.168.1.101 to start client...
[+] Starting client on 192.168.1.101...
```


