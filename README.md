# LAMN - Local Area Machine Network
A comprehensive machine monitoring system with client-server architecture for real-time resource tracking across your infrastructure.

---

## Overview

LAMN consists of two main components:
1. **Client Launcher** - Deploys monitoring clients across multiple machines
2. **Monitoring Server** - Collects, logs, and visualizes machine metrics in real-time

---

## Features

### Client Management
- Launches `lamn` clients remotely via SSH
- Uses `screen` to ensure background execution
- Reads configuration from JSON files in your home directory
- Automatically creates config files if missing
- Validates required config fields on startup

### Monitoring Server
- **Real-time data collection** from all connected clients
- **CSV-based logging** for efficient data storage
- **Interactive web dashboard** with live charts and tables
- **Time-series visualization** showing resource trends over time
- **Machine status cards** with progress bars
- **Auto-refresh** capabilities
- **CSV download** for external analysis

---

## Dashboard Features

The web interface provides:
- **📈 Time-series plots** - CPU, Memory, Disk, GPU usage over time
- **💻 Status cards** - Real-time overview of each machine
- **📋 Detailed tables** - Complete machine specifications and metrics
- **🔄 Auto-refresh** - Updates every 30 seconds
- **📱 Mobile-friendly** - Responsive design that works everywhere

---

## Configuration

### Client Configuration

#### `~/.lamn_config.json` (required)
Stores global defaults used for all agents:
```json
{
  "conda_env": "your_conda_env",
  "screen_name": "lamn_client",
  "launch_cmd": "python ~/lamn/lamn/cli.py client start"
}
```

#### `~/.agents.json` (required)
List of machine IPs to monitor:
```json
[
  "10.20.111.24",
  "10.20.111.109", 
  "10.20.111.14",
  "10.20.113.27",
  "192.168.1.100"
]
```

If these files don't exist, they will be auto-created and the script will guide you through setup.

### Server Configuration

The monitoring server automatically reads agent IPs from the same `~/.agents.json` file and polls each machine every 30 seconds.

---

## Installation & Usage

### 1. Launch Monitoring Clients
Deploy clients across your infrastructure:
```bash
python start_clients.py --username <ssh_username>
```

This will:
- SSH into each machine from `~/.agents.json`
- Check if a client is already running
- Start the lamn client in a screen session if needed

### 2. Start Monitoring Server
Launch the central monitoring server:
```bash
python server.py
```

The server will:
- Start polling all agents every 30 seconds
- Log data to `logs/machine_metrics.csv`
- Serve the web dashboard on `http://localhost:8000`

### 3. Access the Dashboard
Open your browser and navigate to:
- `http://localhost:8000/hybrid` - Full dashboard with charts and tables
- `http://localhost:8000/download_csv` - Download raw CSV data
- `http://localhost:8000/csv_summary` - JSON summary of current status

---

## Data Format

Machine metrics are logged in CSV format with the following columns:
```csv
timestamp,ip,hostname,cpu_percent,memory_percent,disk_percent,gpu_percent,total_memory_gb,total_disk_gb,cpu_model,gpu_model,os_info
```

Example data:
```csv
2025-06-17 20:30:00,10.54.113.24, test1.xxx.yyy.zzz,2.6,13.2,75.32,0,62.3,36.45,INTEL(R) XEON(R) GOLD 5515+,No GPU,Linux 5.14.0
```

---

## Web Interface Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Default dashboard |
| `/hybrid` | Complete dashboard with charts, cards, and tables |
| `/metrics` | Real-time JSON metrics from all machines |
| `/csv_data` | CSV data as JSON for charts |
| `/csv_summary` | Summary statistics in JSON format |
| `/download_csv` | Download the complete CSV file |

---

## Requirements

### For Client Machines
- SSH access configured
- `screen` installed
- `conda` environment with Python 3.6+
- LAMN client software installed

### For Monitoring Server
- Python 3.6+
- Required packages: `flask`, `pandas`, `requests`
- Network access to all client machines

---

## Example Output

### Client Launcher
```
[+] Connecting to 10.10.100.24 to start client...
[+] Starting client on 10.10.100.24...
[+] Connecting to 10.10.100.109 to start client...
[!] Client already running on 10.10.100.109 (screen lamn_client)
```

### Monitoring Server
```
Starting machine monitoring...
Logged: test1.xxx.yyy.zzz - CPU:2.6% MEM:13.2% DISK:75.3%
Logged: test2.xxx.yyy.zzz - CPU:0.4% MEM:2.7% DISK:23.2%
Machine data will be logged to: logs/machine_metrics.csv
View dashboard at: http://localhost:8000/hybrid
```

---

## 🔧 Troubleshooting

### Common Issues

1. **"Client not reachable"** - Check SSH connectivity and firewall rules
2. **"Screen session not found"** - Ensure screen is installed on client machines
3. **"Conda environment not found"** - Verify conda environment name in config
4. **"Chart.js errors"** - Use the `/hybrid` endpoint which doesn't require external libraries

### Debug Mode
For detailed logging, check:
- Client logs in screen sessions: `screen -r lamn_client`
- Server logs in terminal output
- Browser developer console (F12) for web interface issues

---

## 🎉 Quick Start Guide

1. **Clone and setup:**
   ```bash
   git clone <repository>
   cd lamn-client-launcher
   ```

2. **Configure your machines:**
   ```bash
   # Edit ~/.agents.json with your machine IPs
   # Edit ~/.lamn_config.json with your settings
   ```

3. **Deploy clients:**
   ```bash
   python start_clients.py --username your_ssh_user
   ```

4. **Start monitoring:**
   ```bash
   python server.py
   ```

5. **Open dashboard:**
   ```
   http://localhost:8000/hybrid
   ```
