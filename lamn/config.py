import getpass
import json
import os

CONFIG_PATH = os.path.expanduser("~/.agents.json")
SETTINGS_PATH = os.path.expanduser("~/.lamn_config.json")

DEFAULT_SETTINGS = {
    "ssh_user": getpass.getuser(),
    "conda_env": None,
    "remote_python": "python3",
    "poll_interval": 15,
    "connect_timeout": 3,
    "ssh_options": [
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ControlMaster=auto",
        "-o", "ControlPath=~/.ssh/lamn-%r@%h:%p",
        "-o", "ControlPersist=60s",
    ],
}


def load_agents():
    if not os.path.exists(CONFIG_PATH):
        save_agents([])
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def save_agents(agents):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(agents, f, indent=2)


def add_agent(ip):
    agents = load_agents()
    if ip not in agents:
        agents.append(ip)
        save_agents(agents)
        return True
    return False


def remove_agent(ip):
    agents = load_agents()
    if ip in agents:
        agents.remove(ip)
        save_agents(agents)
        return True
    return False


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, 'r') as f:
            try:
                user = json.load(f)
            except json.JSONDecodeError:
                user = {}
        settings.update({k: v for k, v in user.items() if v is not None})
    return settings
