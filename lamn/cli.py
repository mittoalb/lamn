#!/usr/bin/env python3
import argparse
import logging
import requests
from lamn import server, client
from lamn.config import add_agent, load_agents

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def display_terminal_metrics(url):
    """
    Fetch metrics from the central server and display them in the terminal.
    """
    try:
        response = requests.get(url, timeout=5)
        metrics = response.json()
    except Exception as e:
        print("Error fetching metrics from", url, ":", e)
        return

    headers = ["Host", "CPU (%)", "Memory (%)", "Disk Read", "Disk Write", "GPU (%)", "Timestamp", "Status"]
    table = []
    for ip, data in metrics.items():
        if "error" in data:
            row = [ip, "N/A", "N/A", "N/A", "N/A", "N/A", "", data.get("error", "Error")]
        else:
            host_label = data.get("host", ip)
            row = [
                f"{host_label} ({ip})",
                data.get("cpu", "N/A"),
                data.get("memory", "N/A"),
                data.get("disk_read_bytes", "N/A"),
                data.get("disk_write_bytes", "N/A"),
                data.get("gpu", "N/A"),
                data.get("timestamp", "N/A"),
                "OK"
            ]
        table.append(row)

    try:
        from tabulate import tabulate
        print(tabulate(table, headers=headers, tablefmt="grid"))
    except ImportError:
        # Fallback if tabulate is not installed.
        print(headers)
        for row in table:
            print(row)

def main():
    parser = argparse.ArgumentParser(description='lamn - LAN Monitoring Tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Server commands
    server_parser = subparsers.add_parser('server', help='Manage server commands')
    server_parser.add_argument('action', choices=['start', 'stop'], help='Start or stop the server')

    # Client commands (including listing agents)
    client_parser = subparsers.add_parser('client', help='Manage client commands')
    client_parser.add_argument('action', choices=['start', 'stop', 'list'], help='Start, stop or list configured agents')

    # Add command to add a new agent IP address.
    add_parser = subparsers.add_parser('add', help='Add an agent IP address to monitor')
    add_parser.add_argument('ip_address', help='IP address of the agent to add')

    # Terminal command: display central server metrics in terminal.
    terminal_parser = subparsers.add_parser('terminal', help='Display central server metrics in the terminal')
    terminal_parser.add_argument('--url', default='http://127.0.0.1:8000/metrics', help='Central server metrics URL')
    
    # Add command to remove an agent IP address.
    remove_parser = subparsers.add_parser('remove', help='Remove an agent IP address from monitoring')
    remove_parser.add_argument('ip_address', help='IP address of the agent to remove')


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
    elif args.command == 'terminal':
        display_terminal_metrics(args.url)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
