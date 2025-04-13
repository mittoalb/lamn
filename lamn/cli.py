import argparse
import logging
import requests
from lamn import server, client
from lamn.config import add_agent, load_agents

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='lamn - LAN Monitoring Tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    server_parser = subparsers.add_parser('server', help='Manage server commands')
    server_parser.add_argument('action', choices=['start', 'stop'], help='start or stop the server')

    client_parser = subparsers.add_parser('client', help='Manage client commands')
    client_parser.add_argument('action', choices=['start', 'stop', 'list'], 
                               help='start, stop or list configured agents')

    add_parser = subparsers.add_parser('add', help='Add an agent IP address to monitor')
    add_parser.add_argument('ip_address', help='IP address of the agent to add')

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
    else:
        parser.print_help()

if __name__ == '__main__':
    main()

