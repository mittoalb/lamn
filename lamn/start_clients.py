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


def start_client_on(ip, username, password, conda_env, screen_name, launch_cmd):
    print(f"[+] Connecting to {ip} to start client...")

    ssh_cmd = f"ssh {username}@{ip} 'bash -s'"
    print(f"[DEBUG] Running SSH command: {ssh_cmd}")

    remote_script = f"""
        screen -dmS {screen_name} bash -c '
            source ~/.bashrc
            conda activate {conda_env}
            {launch_cmd}
        '
        echo "Client launched OK"
    """

    try:
        child = pexpect.spawn(ssh_cmd, timeout=30)

        i = child.expect([
            "Are you sure you want to continue connecting",  # first-time trust prompt
            "password:",
            pexpect.EOF,
            pexpect.TIMEOUT
        ])

        if i == 0:
            print(f"[{ip}] Accepting new host key")
            child.sendline("yes")
            child.expect("password:")
            child.sendline(password)
        elif i == 1:
            print(f"[{ip}] Sending password")
            child.sendline(password)
        elif i in [2, 3]:
            raise RuntimeError(f"[{ip}] SSH connection failed (EOF or TIMEOUT)")

        # Send the remote script
        child.sendline(remote_script)
        child.expect(pexpect.EOF)

        output = child.before.decode(errors="ignore").strip()
        print(f"[{ip}] Remote output:\n{output}")

        if "Client launched OK" not in output:
            raise RuntimeError(f"[{ip}] Client may not have launched correctly.")

    except Exception as e:
        print(f"[X] Error starting client on {ip}: {e}")


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