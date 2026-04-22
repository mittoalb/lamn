#!/usr/bin/env python3
import argparse
import logging

import requests

from lamn import server
from lamn.config import add_agent, load_agents, remove_agent

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("lamn.cli")


def display_terminal_metrics(url):
    try:
        response = requests.get(url, timeout=5)
        metrics = response.json()
    except Exception as e:
        print("Error fetching metrics from", url, ":", e)
        return

    headers = ["Host", "CPU (%)", "Memory (%)", "Disk Used", "Disk Total",
               "Disk (%)", "GPU (%)", "Last good", "Status"]
    table = []

    for ip, data in metrics.items():
        status = data.get("_status") or ("stale" if data.get("_last_success") else "unknown")
        has_data = data.get("_last_success") or data.get("host")
        if not has_data:
            table.append([ip, "–", "–", "–", "–", "–", "–", "",
                         data.get("_last_error") or status])
            continue
        host_label = data.get("host", ip)
        specs = data.get("specs", {})
        disk_summary = specs.get("disk_summary", {})
        table.append([
            f"{host_label} ({ip})",
            data.get("cpu", "N/A"),
            data.get("memory", "N/A"),
            disk_summary.get("total_used_human", "N/A"),
            disk_summary.get("total_space_human", "N/A"),
            disk_summary.get("percent_used", "N/A"),
            data.get("gpu", "N/A"),
            data.get("_last_success", "N/A"),
            status.upper(),
        ])

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

    server_parser = subparsers.add_parser('server', help='Manage the server')
    server_parser.add_argument('action', choices=['start', 'stop'])

    add_parser = subparsers.add_parser('add', help='Add an agent IP to monitor')
    add_parser.add_argument('ip_address')

    remove_parser = subparsers.add_parser('remove', help='Remove an agent IP')
    remove_parser.add_argument('ip_address')

    subparsers.add_parser('list', help='List all agent IPs')

    terminal_parser = subparsers.add_parser(
        'terminal', help='Display server metrics in the terminal')
    terminal_parser.add_argument(
        '--url', default='http://127.0.0.1:8000/metrics')

    subparsers.add_parser(
        'probe', help='Run the metrics probe locally (for debugging)')

    args = parser.parse_args()

    if args.command == 'server':
        if args.action == 'start':
            server.start()
        elif args.action == 'stop':
            try:
                r = requests.post('http://127.0.0.1:8000/shutdown')
                print(r.text)
            except Exception as e:
                logger.error("Error stopping server: %s", e)

    elif args.command == 'add':
        if add_agent(args.ip_address):
            print(f"Agent {args.ip_address} added successfully.")
        else:
            print(f"Agent {args.ip_address} is already in the list.")

    elif args.command == 'remove':
        if remove_agent(args.ip_address):
            print(f"Agent {args.ip_address} removed successfully.")
        else:
            print(f"Agent {args.ip_address} was not in the list.")

    elif args.command == 'list':
        agents = load_agents()
        if agents:
            print("Configured Agents:")
            for ip in agents:
                print(ip)
        else:
            print("No configured agents.")

    elif args.command == 'terminal':
        display_terminal_metrics(args.url)

    elif args.command == 'probe':
        from lamn.probe import collect
        import json as _json
        print(_json.dumps(collect(), indent=2))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
