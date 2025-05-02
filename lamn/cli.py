#!/usr/bin/env python3
import argparse
import logging
import subprocess
import requests
from lamn import server, client
from lamn.config import add_agent, load_agents, remove_agent

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("lamn.cli")

def screen_exists(name):
    try:
        result = subprocess.check_output(f"screen -ls | grep {name}", shell=True)
        return name in result.decode()
    except subprocess.CalledProcessError:
        return False

def display_terminal_metrics(url):
    try:
        response = requests.get(url, timeout=5)
        metrics = response.json()
    except Exception as e:
        print("Error fetching metrics from", url, ":", e)
        return

    headers = ["Host", "CPU (%)", "Memory (%)", "Disk Used", "Disk Total", "Disk (%)", "GPU (%)", "Timestamp", "Status"]
    table = []

    for ip, data in metrics.items():
        if "error" in data:
            row = [ip, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "", data.get("error", "Error")]
        else:
            host_label = data.get("host", ip)
            specs = data.get("specs", {})
            disk_summary = specs.get("disk_summary", {})
            row = [
                f"{host_label} ({ip})",
                data.get("cpu", "N/A"),
                data.get("memory", "N/A"),
                disk_summary.get("total_used_human", "N/A"),
                disk_summary.get("total_space_human", "N/A"),
                disk_summary.get("percent_used", "N/A"),
                data.get("gpu", "N/A"),
                data.get("timestamp", "N/A"),
                "OK"
            ]
        table.append(row)

    try:
        from tabulate import tabulate
        print(tabulate(table, headers=headers, tablefmt="grid"))
    except ImportError:
        print(headers)
        for row in table:
            print(row)

def main():
    parser = argparse.ArgumentParser(description='lamn - LAN Monitoring Tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    server_parser = subparsers.add_parser('server', help='Manage server commands')
    server_parser.add_argument('action', choices=['start', 'stop'], help='Start or stop the server')

    client_parser = subparsers.add_parser('client', help='Manage client commands')
    client_parser.add_argument('action', choices=['start', 'stop', 'list'], help='Start, stop or list configured agents')

    add_parser = subparsers.add_parser('add', help='Add an agent IP address to monitor')
    add_parser.add_argument('ip_address', help='IP address of the agent to add')

    remove_parser = subparsers.add_parser('remove', help='Remove an agent IP address from monitoring')
    remove_parser.add_argument('ip_address', help='IP address of the agent to remove')

    terminal_parser = subparsers.add_parser('terminal', help='Display central server metrics in the terminal')
    terminal_parser.add_argument('--url', default='http://127.0.0.1:8000/metrics', help='Central server metrics URL')

    list_parser = subparsers.add_parser('list', help='List all agent IPs from agents.json')

    start_parser = subparsers.add_parser('start', help='Start components')
    start_parser.add_argument('target', choices=['all'], help='Start the server and all remote clients')

    stop_parser = subparsers.add_parser('stop', help='Stop components')
    stop_parser.add_argument('target', choices=['all'], help='Stop the server and all remote clients')

    restart_parser = subparsers.add_parser('restart', help='Restart components')
    restart_parser.add_argument('target', choices=['all'], help='Restart the server and all remote clients')

    args = parser.parse_args()

    if args.command == 'server':
        if args.action == 'start':
            server.start()
        elif args.action == 'stop':
            try:
                response = requests.post('http://127.0.0.1:8000/shutdown')
                print(response.text)
            except Exception as e:
                logger.error("Error stopping server: " + str(e))

    elif args.command == 'client':
        if args.action == 'start':
            client.start()
        elif args.action == 'stop':
            try:
                response = requests.post('http://127.0.0.1:5000/shutdown')
                print(response.text)
            except Exception as e:
                logger.error("Error stopping client: " + str(e))
        elif args.action == 'list':
            agents = load_agents()
            if agents:
                print("Configured Agents:")
                for ip in agents:
                    print(ip)
            else:
                print("No configured agents.")

    elif args.command == 'add':
        added = add_agent(args.ip_address)
        if added:
            print(f"Agent {args.ip_address} added successfully.")
        else:
            print(f"Agent {args.ip_address} is already in the list.")

    elif args.command == 'remove':
        removed = remove_agent(args.ip_address)
        if removed:
            print(f"Agent {args.ip_address} removed successfully.")
        else:
            print(f"Agent {args.ip_address} was not in the list.")

    elif args.command == 'terminal':
        display_terminal_metrics(args.url)

    elif args.command == 'list':
        agents = load_agents()
        if agents:
            print("Configured Agents:")
            for ip in agents:
                print(ip)
        else:
            print("No configured agents.")
    
    elif args.command == 'start' and args.target == 'all':
        # Prompt for SSH username first
        username = input("Enter SSH username: ").strip()

        # Start remote clients only
        logger.info("Launching remote clients using start_clients.py...")
        subprocess.run(
            f'python ~/Software/lamn/lamn/start_clients.py --username {username}',
            shell=True
        )

        logger.info("Done. Server not started — please launch it manually.")


    elif args.command == 'stop' and args.target == 'all':
        username = input("Enter SSH username: ").strip()

        logger.info("Stopping lamn server...")
        subprocess.run('screen -S lamn_server -X quit', shell=True)

        agents = load_agents()
        for ip in agents:
            logger.info(f"Stopping client on {ip}...")
            subprocess.run(
                f'ssh {username}@{ip} "screen -S lamn_client -X quit"',
                shell=True
            )

    elif args.command == 'restart' and args.target == 'all':
        username = input("Enter SSH username: ").strip()

        logger.info("Stopping lamn server and clients...")
        subprocess.run('screen -S lamn_server -X quit', shell=True)

        agents = load_agents()
        for ip in agents:
            logger.info(f"Stopping client on {ip}...")
            subprocess.run(
                f'ssh {username}@{ip} "screen -S lamn_client -X quit"',
                shell=True
            )

        logger.info("Restarting remote clients...")
        subprocess.run(
            f'python ~/Software/lamn/lamn/start_clients.py --username {username}',
            shell=True
        )

        if screen_exists("lamn_server"):
            logger.info("lamn_server screen session already running after restart. Skipping server start.")
        else:
            logger.info("Restarting lamn server in screen...")
            subprocess.run(
                'screen -dmS lamn_server bash -c "source ~/.bashrc && conda activate lamn-env && python ~/Software/lamn/lamn/cli.py server start"',
                shell=True
            )

    else:
        parser.print_help()

if __name__ == '__main__':
    main()
