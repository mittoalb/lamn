import os
import json

CONFIG_PATH = os.path.expanduser("~/.agents.json")  # Global per-user config file

def load_agents():
    if not os.path.exists(CONFIG_PATH):
        # Ensure the file exists and is initialized as an empty list
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
