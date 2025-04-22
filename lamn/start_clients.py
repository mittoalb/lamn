#!/usr/bin/env python3
import os
import json
import argparse
import textwrap
import sys
import getpass
import pexpect

# --- Config paths ---
CONFIG_FILE = os.path.expanduser("~/.lamn_config.json")
AGENTS_FILE = os.path.expanduser("~/.agents.json")

# --- Load config from ~/.lamn_config.json ---
def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"[!] Config file not found: {CONFIG_FILE}")
        with open(CONFIG_FILE, 'w') as f:
            json.dump({}, f, indent=2)
        print(f"[+] Created empty config file. Please edit it with required fields and rerun.")
        sys.exit(1)

    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)

    required_keys = ['conda_env', 'screen_name', 'launch_cmd']
    for key in required_keys:
        if key not in config:
            print(f"[X] Missing required key '{key}' in config.")
            sys.exit(1)

    return config['conda_env'], config['screen_name'], config['launch_cmd']

# --- Load agents from file (create if missing) ---
def load_agents():
    if not os.path.exists(AGENTS_FILE):
        with open(AGENTS_FILE, "w") as f:
            json.dump([], f)
    with open(AGENTS_FILE, "r") as f:
        return json.load(f)

# --- Use pexpect to run SSH command with password ---
def start_client_on(ip, username, password, conda_env, screen_name, launch_cmd):
    print(f"[+] Connecting to {ip} to start client...")

    remote_script = textwrap.dedent(f"""\
        if screen -list | grep -q {screen_name}; then
            echo "[!] Client already running on {ip} (screen {screen_name})"
        else
            echo "[+] Starting client on {ip}..."
            source ~/.bashrc
            conda activate {conda_env}
            screen -dmS {screen_name} {launch_cmd}
        fi
    """)

    ssh_cmd = f"ssh {username}@{ip} 'bash -s'"
    try:
        child = pexpect.spawn(ssh_cmd, timeout=30)
        i = child.expect(["yes/no", "password:", pexpect.EOF, pexpect.TIMEOUT])

        if i == 0:
            child.sendline("yes")
            child.expect("password:")
            child.sendline(password)
        elif i == 1:
            child.sendline(password)
        elif i in (2, 3):
            print(f"[X] Failed to connect to {ip}")
            return

        child.sendline(remote_script)
        child.expect(pexpect.EOF)
        output = child.before.decode(errors="ignore").strip()
        print(output)

    except Exception as e:
        print(f"[X] Error on {ip}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Start lamn clients on all configured agents")
    parser.add_argument('--username', required=True, help="SSH username to connect with")
    args = parser.parse_args()

    password = getpass.getpass("Enter SSH password: ")
    conda_env, screen_name, launch_cmd = load_config()
    agents = load_agents()

    if not agents:
        print("No agents found in ~/.agents.json.")
        return

    for ip in agents:
        try:
            start_client_on(ip, args.username, password, conda_env, screen_name, launch_cmd)
        except Exception as e:
            print(f"[X] Error starting client on {ip}: {e}")

if __name__ == "__main__":
    main()