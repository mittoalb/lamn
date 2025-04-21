# lamn/config.py
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'agents.json')

def load_agents():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    else:
        return []

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
    

