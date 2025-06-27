#!/usr/bin/env python3
"""
SOCKS Proxy Test Utility for LAMN
Tests SOCKS proxy connectivity and configuration
"""

import json
import os
import sys
import socks
import socket
import requests

CONFIG_FILE = os.path.expanduser("~/.lamn_config.json")

def load_existing_config():
    """Load existing LAMN configuration"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def test_socks_proxy(host, port):
    """Test SOCKS proxy connectivity"""
    print(f"\nTesting SOCKS proxy {host}:{port}...")
    
    try:
        # Test 1: Basic socket connection
        test_sock = socks.socksocket()
        test_sock.set_proxy(socks.SOCKS5, host, port)
        test_sock.settimeout(10)
        test_sock.connect(("8.8.8.8", 53))  # Google DNS
        test_sock.close()
        print("Basic SOCKS connection successful")
        
        # Test 2: HTTP request through SOCKS
        session = requests.Session()
        proxy_url = f'socks5://{host}:{port}'
        session.proxies = {'http': proxy_url, 'https': proxy_url}
        
        response = session.get('http://httpbin.org/ip', timeout=10)
        if response.status_code == 200:
            print("HTTP through SOCKS successful")
            print(f"  External IP: {response.json().get('origin', 'Unknown')}")
        else:
            print(f"HTTP request failed with status: {response.status_code}")
            
        return True
        
    except Exception as e:
        print(f"SOCKS proxy test failed: {e}")
        return False

def test_direct_connection(target_ip, target_port=5000):
    """Test direct connection to target without SOCKS"""
    print(f"\nTesting direct connection to {target_ip}:{target_port}...")
    
    try:
        response = requests.get(f'http://{target_ip}:{target_port}/metrics', timeout=5)
        print("Direct connection successful")
        return True
    except Exception as e:
        print(f"Direct connection failed: {e}")
        return False

def test_socks_to_target(socks_host, socks_port, target_ip, target_port=5000):
    """Test connection to target through SOCKS proxy"""
    print(f"\nTesting connection to {target_ip}:{target_port} through SOCKS...")
    
    try:
        session = requests.Session()
        proxy_url = f'socks5://{socks_host}:{socks_port}'
        session.proxies = {'http': proxy_url, 'https': proxy_url}
        
        response = session.get(f'http://{target_ip}:{target_port}/metrics', timeout=10)
        if response.status_code == 200:
            print("Connection to target through SOCKS successful")
            print(f"  Response: {response.json() if response.content else 'Empty'}")
            return True
        else:
            print(f"Target responded with status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Connection to target through SOCKS failed: {e}")
        return False

def save_socks_config(config, socks_host, socks_port, enabled=True):
    """Save SOCKS configuration to LAMN config file"""
    config['socks_proxy'] = {
        'enabled': enabled,
        'host': socks_host,
        'port': socks_port,
        'type': 'socks5'
    }
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"SOCKS configuration saved to {CONFIG_FILE}")

def main():
    print("LAMN SOCKS Proxy Test Utility")
    print("=" * 50)
    
    # Load existing config
    config = load_existing_config()
    print(f"Config file: {CONFIG_FILE}")
    
    # Get SOCKS proxy settings
    print("\nSOCKS Proxy Configuration:")
    
    # Default values
    default_host = config.get('socks_proxy', {}).get('host', '127.0.0.1')
    default_port = config.get('socks_proxy', {}).get('port', 8080)
    
    socks_host = input(f"SOCKS proxy host [{default_host}]: ").strip() or default_host
    socks_port_input = input(f"SOCKS proxy port [{default_port}]: ").strip()
    socks_port = int(socks_port_input) if socks_port_input else default_port
    
    # Test SOCKS proxy
    if test_socks_proxy(socks_host, socks_port):
        enable_socks = True
    else:
        print("\nSOCKS proxy test failed!")
        response = input("Do you want to enable SOCKS anyway? (y/N): ").lower()
        enable_socks = response.startswith('y')
    
    # Test connection to targets if we have agent IPs
    agents_file = os.path.expanduser('~/.agents.json')
    if os.path.exists(agents_file):
        with open(agents_file, 'r') as f:
            agents = json.load(f)
        
        if agents and enable_socks:
            print(f"\nFound {len(agents)} agents in ~/.agents.json")
            test_agent = agents[0]
            
            # Test direct connection first
            test_direct_connection(test_agent)
            
            # Test through SOCKS
            test_socks_to_target(socks_host, socks_port, test_agent)
    
    # Save configuration
    save_socks_config(config, socks_host, socks_port, enable_socks)
    
    print("\n" + "=" * 50)
    if enable_socks:
        print("SOCKS proxy configuration complete!")
        print(f"  Proxy: {socks_host}:{socks_port}")
        print("  Your LAMN server will now use the SOCKS proxy")
    else:
        print("SOCKS proxy disabled")
        print("  Your LAMN server will use direct connections")
    
    print("\nNext steps:")
    print("1. Make sure your SOCKS tunnel is running")
    print("2. Start your LAMN server: python server.py")
    print("3. Monitor the output for connection status")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nConfiguration cancelled by user")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
