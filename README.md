# lamn - LAN Monitoring Tool

lamn is a lightweight, Python-based tool for monitoring system performance across a Local Area Network (LAN). It aggregates metrics such as CPU usage, memory usage, disk I/O, and GPU utilization from multiple machines using a simple HTTP-based agent and presents the data in a web-accessible dashboard.



## Features

- **Agent and Server Architecture**  
  Deploy a client (agent) on each machine to report metrics, and aggregate the data on a central server.
  
- **Real-Time Monitoring**  
  View live updates of performance data, including CPU, memory, disk I/O, and GPU usage.

- **Expandable Hardware Specs**  
  Click on a monitored host’s details to reveal additional hardware information such as OS details, CPU model, GPU name, total RAM, disk capacity, and network connectivity.

- **Command-Line Interface (CLI)**  
  Use simple commands to start/stop services and add new agents:
  ```bash
  lamn server start
  lamn client start
  lamn server stop
  lamn client stop
  lamn add <IP address>


## Usage

  Start the Central Server
  Run the following command on the machine designated as the central server:
  ```bash
  lamn server start
  ```

  The server runs on port 8000 by default. Open your browser and navigate to http://<server-ip>:8000 to view the dashboard.

  Start a Client (Agent)
  On each machine you wish to monitor, run:

  ```bash
  lamn client start
  ```
  
  The client runs on port 5000 by default and serves its metrics at /metrics.

  Add an Agent
  To add an agent IP for monitoring:

  ```bash
  lamn add <IP address>
  ```
  Stop Services
  Stop the server or client using:

  ```bash
  lamn server stop
  lamn client stop
  ```
  Once you create and save the file, it's ready to be committed to your repository.



## Installation
  ```bash
  git clone https://github.com/YourUserName/lamn.git
  cd lamn
  pip install -e .
