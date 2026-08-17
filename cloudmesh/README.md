<div align="center">

# CloudMesh

### One Console to Control Them All

Connect multiple devices and servers into one unified resource pool.
Monitor, manage, and distribute workloads from a single terminal.

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-blue?style=for-the-badge)]()
[![Commands](https://img.shields.io/badge/Commands-48-orange?style=for-the-badge)]()
[![Stars](https://img.shields.io/github/stars/MrAli88708/CloudMesh?style=for-the-badge&color=yellow)](https://github.com/MrAli88708/CloudMesh/stargazers)

<br>

```
 __  __           _        ____
|  \/  | ___  ___| |__    / ___|___  _ __ ___
| |\/| |/ _ \/ __| '_ \  | |   / _ \| '__/ _ \
| |  | |  __/\__ \ | | | | |__| (_) | | |  __/
|_|  |_|\___||___/_| |_|  \____\___/|_|  \___|
```

**48 commands** | **Auto-discovery** | **Real-time monitoring** | **GPU telemetry**

</div>

---

## Why CloudMesh?

Managing multiple servers shouldn't mean juggling 10 SSH windows. CloudMesh gives you **one command** to control everything.

| Problem | CloudMesh Solution |
|---------|-------------------|
| SSH into each server manually | `cm run "command"` - run on all servers at once |
| No visibility into resource usage | `cm monitor` - live dashboard for all nodes |
| GPU servers hard to manage | `cm node gpu` - GPU telemetry from any node |
| No way to distribute work | `cm slice` - auto-slice tasks across servers by resources |
| Miss server alerts | `cm notify` - Telegram/Discord alerts |

---

## Quick Start

### Windows
1. Download [`cm_for-windows.bat`](cm_for-windows.bat) from this repo
2. Double-click to run
3. Done! Use `cm --help` to see all commands

### Linux
```bash
# Download and run - that's it
curl -sL https://raw.githubusercontent.com/MrAli88708/CloudMesh/main/cm_for-linux.sh -o cm.sh
chmod +x cm.sh && ./cm.sh
```

### First Steps
```bash
cm --help              # See all 48 commands
cm interactive         # Interactive TUI menu
cm monitor --local     # Monitor this machine
cm discover 192.168.1  # Scan your network for nodes
```

---

## Architecture

```
                        +-----------------+
                        |   YOUR LAPTOP   |
                        |   (Controller)  |
                        +--------+--------+
                                 |
                  +--------------+--------------+
                  |              |              |
            SSH |         TCP 9999 |      TCP 9999 |
                  |              |              |
          +-------v--+    +-----v----+   +-----v----+
          |  Linux   |    | Windows  |   |   GPU    |
          |  Server  |    |  Server  |   |  Server  |
          +----------+    +----------+   +----------+
```

**Two ways to connect:**
- **SSH** - For any server with SSH access
- **TCP Node** - Lightweight agent (2MB) on any device

---

## Features

<details>
<summary><b>Core - Server Management</b></summary>

| Command | Description |
|---------|-------------|
| `cm server add` | Add server via SSH |
| `cm server list` | List all servers |
| `cm server test` | Test connection |
| `cm server info` | Server details |
| `cm run "cmd"` | Run command on all servers |
| `cm monitor` | Real-time resource monitoring |
| `cm dashboard` | Live dashboard |

</details>

<details>
<summary><b>Cloud Nodes - Lightweight Agents</b></summary>

| Command | Description |
|---------|-------------|
| `cm node add` | Add a node |
| `cm node install` | Remote install via SSH |
| `cm node monitor` | Monitor node resources |
| `cm node gpu` | GPU telemetry |
| `cm node exec` | Execute command on node |
| `cm node job start` | Start async job |
| `cm node job status` | Check job status |
| `cm node dashboard` | Node overview |

</details>

<details>
<summary><b>Network & Discovery</b></summary>

| Command | Description |
|---------|-------------|
| `cm discover` | Scan subnet for nodes |
| `cm ping` | Ping all servers |
| `cm scan` | Scan subnet for ports |
| `cm speed` | Network latency test |
| `cm network` | Network interfaces |
| `cm map` | Visual network overview |

</details>

<details>
<summary><b>System Monitoring</b></summary>

| Command | Description |
|---------|-------------|
| `cm monitor` | CPU/RAM/Disk live view |
| `cm top` | Top processes |
| `cm disk` | Disk usage per mount |
| `cm uptime` | System uptime |
| `cm who` | Logged-in users |
| `cm logs` | System logs |
| `cm gpu` | GPU stats |

</details>

<details>
<summary><b>File Operations</b></summary>

| Command | Description |
|---------|-------------|
| `cm transfer` | Upload/download files |
| `cm sync` | Sync directories |
| `cm autosync` | Auto-sync folders |
| `cm find` | Search for files |
| `cm slice` | Distribute files across servers |

</details>

<details>
<summary><b>Advanced Features</b></summary>

| Command | Description |
|---------|-------------|
| `cm bench` | CPU/RAM/Disk benchmark |
| `cm schedule` | Recurring commands |
| `cm notify` | Telegram/Discord alerts |
| `cm api` | REST API server |
| `cm audit` | Security audit |
| `cm template` | Reusable command templates |
| `cm profile` | Config profiles |
| `cm alerts` | Threshold alerts |

</details>

<details>
<summary><b>Utilities</b></summary>

| Command | Description |
|---------|-------------|
| `cm encrypt`/`decrypt` | File encryption |
| `cm export`/`import` | Config backup |
| `cm cleanup` | Remove old files |
| `cm report` | Usage report |
| `cm alias` | Command shortcuts |
| `cm version` | Version info |
| `cm history` | Command history |

</details>

---

## Examples

### Add a Server
```bash
cm server add -n prod-server -H 192.168.1.100 -u root -k ~/.ssh/id_rsa
cm server test -n prod-server
```

### Monitor Everything
```bash
cm monitor           # All servers
cm monitor -n prod   # Specific server
cm node gpu          # GPU usage on all nodes
```

### Run Commands Everywhere
```bash
cm run "apt update && apt upgrade -y"        # Update all servers
cm run "df -h" --best                         # Run on best server
cm run "docker ps" -s "web,api"              # Specific servers
```

### Distribute Work
```bash
# Split files across GPU servers
cm slice -f "data_*.csv" -s "gpu1,gpu2,gpu3"

# Start async job
cm node job start -n gpu-server "python train.py" -t 3600
cm node job status -n gpu-server -j abc123
```

### Auto-Discovery
```bash
cm discover 192.168.1.0          # Find nodes on subnet
cm discover 10.0.0 --port 9999   # Custom port
```

### Notifications
```bash
cm notify setup-telegram --token BOT_TOKEN --chat-id CHAT_ID
cm notify setup-discord --webhook WEBHOOK_URL
cm notify send "Server is down!"
```

### Schedule Tasks
```bash
cm schedule add -n monitor "cm ping" -i 300           # Every 5 min
cm schedule add -n cleanup "cm cleanup -d 7" -i 86400  # Daily
cm schedule list                                        # View all
```

---

## Installation Options

| Option | What it does |
|--------|-------------|
| **Fresh Install** | Download installer, double-click, done |
| **Update** | Run installer again, choose "Update" |
| **Factory Reset** | Choose "Factory Reset" - wipes everything |
| **Uninstall** | Choose "Uninstall" - removes completely |

The installer automatically:
- Downloads all files from GitHub
- Installs Python if missing
- Sets up node agent
- Creates virtual environment
- Installs all dependencies

---

## Node Installation

### On the Same Network
```bash
chmod +x cm_for-linux.sh
./cm_for-linux.sh
```

### Remote (via SSH from Controller)
```bash
cm node install -H SERVER_IP -u root -k ~/.ssh/id_rsa
```

### What Gets Installed
```
~/.cloudmesh-node/
  cloudmesh_node.py    # Node agent
  .node_key            # Auth key
  start.sh             # Start script
  stop.sh              # Stop script
  status.sh            # Status script
  cloudmesh-node.service  # Systemd service (auto-created)
```

---

## Project Structure

```
cloudmesh/
  main.py              # CLI entry point (48 commands)
  requirements.txt     # Python dependencies
  README.md            # This file
  core/
    server.py          # SSH server management
    monitor.py         # Resource monitoring
    scheduler.py       # Task scheduling
    node_client.py     # TCP node communication
    jobs.py            # Async job system
    gpu.py             # GPU telemetry
    features.py        # 20 utility features
    advanced.py        # 10 advanced features
    security.py        # Encryption & audit
    transfer.py        # File transfer
    sync.py            # Directory sync
    deploy.py          # Package deployment
    alerts.py          # Threshold alerts
    groups.py          # Device groups
    dashboard.py       # Live dashboard
    tui.py             # Interactive TUI
    history.py         # Command history
    cmdlog.py          # Command logging
    service.py         # Service management
  node/
    cloudmesh_node.py  # Standalone node agent
```

---

## Requirements

| Component | Requirement |
|-----------|------------|
| Controller | Python 3.8+, SSH client |
| Node Agent | Python 3.8+ (auto-installed) |
| OS | Windows 10+, Linux (Ubuntu/Debian/CentOS/Arch) |

### Dependencies (auto-installed)
- `rich` - Beautiful terminal UI
- `paramiko` - SSH connections
- `psutil` - System monitoring
- `cryptography` - File encryption

---

## Troubleshooting

<details>
<summary><b>Download fails from installer</b></summary>

Make sure you have internet access. The installer downloads from GitHub. If behind a proxy, download the files manually from this repo.
</details>

<details>
<summary><b>Node not connecting</b></summary>

```bash
# Check node is running
~/.cloudmesh-node/status.sh

# Restart node
~/.cloudmesh-node/start.sh

# Check port is open
netstat -tlnp | grep 9999
```
</details>

<details>
<summary><b>Auth failed error</b></summary>

```bash
# Get the key from the node
cat ~/.cloudmesh-node/.node_key

# Re-add with correct key
cm node add -n NAME -H HOST -p 9999 -k YOUR_KEY
```
</details>

<details>
<summary><b>Module not found errors</b></summary>

```bash
# Reinstall dependencies
cm version    # Shows Python path
pip install -r requirements.txt
```
</details>

---

## License

MIT License - Free to use, modify, and distribute.

---

<div align="center">

**Made with passion by MRSX PRO**

Star this repo if CloudMesh helps you! It motivates us to keep building.

[Star on GitHub](https://github.com/MrAli88708/CloudMesh)

</div>
