# CloudMesh - The Complete Guide

### Made By MRSX PRO

This is the **complete, exhaustive reference guide** for CloudMesh. Everything you need to know about the tool — every command, every feature, every concept — is explained here in extreme detail. Read this file once and you will know CloudMesh better than most developers know their own tools.

---

## Table of Contents

1. [What is CloudMesh?](#1-what-is-cloudmesh)
2. [Architecture Deep Dive](#2-architecture-deep-dive)
3. [Installation](#3-installation)
4. [First Steps](#4-first-steps)
5. [Server Management](#5-server-management)
6. [Node Management](#6-node-management)
7. [Monitoring & Dashboards](#7-monitoring--dashboards)
8. [Running Commands Remotely](#8-running-commands-remotely)
9. [File Operations](#9-file-operations)
10. [Docker Management](#10-docker-management)
11. [Firewall Management](#11-firewall-management)
12. [SSL Certificate Monitoring](#12-ssl-certificate-monitoring)
13. [Log Aggregation](#13-log-aggregation)
14. [Webhooks & Alerts](#14-webhooks--alerts)
15. [Process Watchers](#15-process-watchers)
16. [ACL (Access Control)](#16-acl-access-control)
17. [SSH Tunnels](#17-ssh-tunnels)
18. [Database Management](#18-database-management)
19. [Scheduling](#19-scheduling)
20. [Notifications](#20-notifications)
21. [Plugins System](#21-plugins-system)
22. [SSH Key Management](#22-ssh-key-management)
23. [Configuration Management](#23-configuration-management)
24. [Shell Completions](#24-shell-completions)
25. [Security Features](#25-security-features)
26. [Ghost Ports (SPA)](#26-ghost-ports-spa)
27. [Tripwire Keys](#27-tripwire-keys)
28. [Emergency Panic Button](#28-emergency-panic-button)
29. [Shamir Panic](#29-shamir-panic)
30. [Remote Panic Rotation](#30-remote-panic-rotation)
31. [Resource Weather Forecast](#31-resource-weather-forecast)
32. [Distributed Trust](#32-distributed-trust)
33. [Job Checkpointing](#33-job-checkpointing)
34. [Command Ledger (Tamper Detection)](#34-command-ledger-tamper-detection)
35. [DDoS Protection](#35-ddos-protection)
36. [Self Update](#36-self-update)
37. [Doctor (Health Check)](#37-doctor-health-check)
38. [Network Discovery](#38-network-discovery)
39. [Benchmarks](#39-benchmarks)
40. [Security Audits](#40-security-audits)
41. [REST API](#41-rest-api)
42. [Interactive TUI](#42-interactive-tui)
43. [Aliases](#43-aliases)
44. [Templates](#44-templates)
45. [Profiles](#45-profiles)
46. [Resource History](#46-resource-history)
47. [Device Groups](#47-device-groups)
48. [Service Management](#48-service-management)
49. [GPU Telemetry](#49-gpu-telemetry)
50. [Project Structure](#50-project-structure)
51. [Contributing](#51-contributing)

---

## 1. What is CloudMesh?

CloudMesh is a **command-line tool** that connects multiple servers and devices into one unified resource pool. Instead of SSHing into 10 different servers, you run one command from your laptop and CloudMesh executes it on all of them.

**Core concept:** You have a **Controller** (your laptop) and one or more **Nodes** (cloud servers, VPS, Raspberry Pis, anything running Python). The controller talks to nodes via SSH or a lightweight TCP agent.

**Key facts:**
- Written in pure Python (3.8+)
- 155+ CLI commands
- Works on Windows and Linux
- Zero web interface — pure terminal
- Open source on GitHub

---

## 2. Architecture Deep Dive

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

### Two Connection Methods

**1. SSH (Traditional)**
- Uses `paramiko` library for SSH connections
- Requires SSH key or password on the remote server
- Supports `StrictHostKeyChecking` (enabled by default for security)
- Good for: any server you can SSH into

**2. TCP Node Agent**
- Lightweight Python agent (single file: `cloudmesh_node.py`)
- Runs as a background service on the remote server
- Communicates on TCP port 9999
- Supports optional TLS encryption
- Supports optional SPA (Ghost Ports) for stealth
- Good for: servers you want persistent monitoring on

### Data Storage

All CloudMesh data is stored locally on your laptop:

```
cloudmesh/
  config.json          # Encrypted server configs (Fernet encryption)
  .secret.key          # Encryption key for config
  command_log.json     # Immutable command ledger (SHA-256 hash chain)
  alerts.json          # Alert rules and history
  .resource_weather.json  # Weather forecast data
  .gossip_trust.json   # Distributed trust data
  .panic_log.json      # Panic event log
  .panic_pending.json  # Pending remote key rotations
  plugins.json         # Plugin registry
  watchers.json        # Process watchers
  webhooks.json        # Webhook configs
  data/
    acl.json           # Access control users/roles
    banned_ips.json    # DDoS protection ban list
    .node_keys.json    # Node auth keys
    cloudmesh.json     # Main config (servers, nodes, settings)
    plugins.json       # Plugin definitions
```

### Node Agent Installation

When you install a node agent, here is what gets placed on the remote server:

```
~/.cloudmesh-node/
  cloudmesh_node.py       # The agent itself
  .node_key               # Auth key for HMAC authentication
  .secret.key             # Fernet encryption key
  start.sh                # Start script (creates systemd service)
  stop.sh                 # Stop script
  status.sh               # Status check script
  cloudmesh-node.service  # Systemd unit file (auto-created)
```

---

## 3. Installation

### Method 1: pip install (Recommended)

```bash
pip install cloudmesh
cm --help
```

### Method 2: Windows Installer

1. Install [Python](https://www.python.org/) first
2. Download `cm_for-windows.bat` from the GitHub repo
3. Double-click the .bat file
4. It downloads everything from GitHub, installs dependencies, creates a shortcut
5. Done! Use `cm` in PowerShell

### Method 3: Linux Installer

```bash
# Install Python first, then:
curl -sL https://raw.githubusercontent.com/MrAli88708/CloudMesh/main/cm_for-linux.sh -o cm.sh
chmod +x cm.sh && ./cm.sh
```

### Updating

```bash
cm update              # Self-update from GitHub (recommended)
pip install --upgrade cloudmesh  # Or via pip
```

### Uninstalling

```bash
pip uninstall cloudmesh
```

---

## 4. First Steps

After installation, these are the first commands to run:

```bash
# See all available commands
cm --help

# Quick status overview
cm status

# Interactive TUI (menu-based interface)
cm interactive

# Monitor your own machine
cm mon --local

# Real-time monitoring dashboard
cm watch

# Add your first server
cm add -n myserver -H 192.168.1.100 -u root -k ~/.ssh/id_rsa

# Test the connection
cm test -n myserver

# Run a command on it
cm run "uptime" -s myserver

# Run on all servers at once
cm run "df -h"

# Run a health check
cm doctor

# Enable shell completions (bash/zsh/powershell)
cm completions bash
```

---

## 5. Server Management

Servers are remote machines connected via SSH. CloudMesh stores their connection info in an encrypted config file.

### Adding a Server

```bash
cm server add -n NAME -H HOST -u USER -p PORT -k KEY_PATH
# Alias: cm add
```

**Parameters:**
- `-n / --name`: A nickname for the server (e.g., "prod-web-1")
- `-H / --host`: IP address or hostname (e.g., "192.168.1.100")
- `-u / --user`: SSH username (e.g., "root")
- `-p / --port`: SSH port (default: 22)
- `-k / --key`: Path to SSH private key (e.g., "~/.ssh/id_rsa")

**Example:**
```bash
cm add -n prod-web -H 203.0.113.50 -u root -k ~/.ssh/id_rsa
cm add -n staging -H 192.168.1.200 -u deploy -p 2222 -k ~/.ssh/deploy_key
```

### Listing Servers

```bash
cm server list
# Alias: cm ls
```

Shows a table with: Name, Host, User, Port, Status.

### Testing Connection

```bash
cm server test -n NAME
# Alias: cm test
```

Pings the server via SSH and shows connection status.

### Server Details

```bash
cm server info -n NAME
# Alias: cm info
```

Shows detailed info: host, user, port, OS type, status, uptime.

### Removing a Server

```bash
cm server remove -n NAME
# Alias: cm rm
```

Disconnects and removes the server from config. Does NOT affect the remote server itself.

---

## 6. Node Management

Nodes are servers running the lightweight TCP agent. They communicate on port 9999 using JSON messages with HMAC authentication.

### Adding a Node

```bash
cm node add -n NAME -H HOST -p PORT -k KEY
```

**Parameters:**
- `-n / --name`: Nickname for the node
- `-H / --host`: IP address
- `-p / --port`: TCP port (default: 9999)
- `-k / --key`: Auth key (must match the key on the node)

### Installing Node Agent Remotely

```bash
cm node install -H HOST -u USER -k SSH_KEY
# Alias: cm nodeinstall
```

This SSHes into the server, downloads the agent from GitHub, installs dependencies, creates systemd service, and starts it. The auth key is generated automatically.

### Listing Nodes

```bash
cm node list
```

### Testing Node Connection

```bash
cm node test -n NAME
```

### Node Details

```bash
cm node info -n NAME
```

### Removing a Node

```bash
cm node remove -n NAME
# Alias: cm rmnode
```

### Node Agent Commands

```bash
# Start the agent
cm node start

# Start with specific options
cm node start --bind 127.0.0.1         # Bind to specific interface
cm node start --port 9999              # Custom TCP port
cm node start --spa                    # Enable Ghost Ports (SPA)
cm node start --spa --spa-port 9998    # Custom UDP port for SPA
cm node start --spa --spa-window 10    # TCP stays open 10s after knock
cm node start --tls-cert cert.pem --tls-key key.pem  # Enable TLS

# Stop the agent
cm node stop

# Check status
cm node status
```

### Node Dashboard

```bash
cm node dashboard
```

Shows an overview of all connected nodes with CPU, RAM, disk, GPU info.

---

## 7. Monitoring & Dashboards

### Basic Monitoring

```bash
cm monitor          # All servers
# Alias: cm mon

cm monitor -n NAME  # Specific server
cm mon --local      # This machine only
```

Shows: CPU%, RAM%, Disk%, swap, uptime for each server.

### Live Dashboard

```bash
cm dashboard
# Alias: cm dash
```

Rich formatted dashboard with per-server resource bars.

### Real-time Monitoring (v2.0.0)

```bash
cm watch
```

Auto-refreshing dashboard that updates every few seconds. Shows CPU, RAM, Disk, and GPU for all nodes in real-time.

### Uptime

```bash
cm uptime           # All servers
cm uptime -n NAME   # Specific server
# Alias: cm up
```

### Disk Usage

```bash
cm disk             # All servers
cm disk -n NAME     # Specific server
# Alias: cm df
```

Shows per-mount disk usage: device, size, used, available, use%, mount point.

### Network Info

```bash
cm network          # All servers
cm network -n NAME  # Specific server
# Alias: cm net
```

Shows network interfaces, IP addresses, status.

### Top Processes

```bash
cm top              # All servers
cm top -n NAME      # Specific server
cm top --sort ram   # Sort by RAM instead of CPU
```

### Logged-in Users

```bash
cm who              # All servers
cm who -n NAME      # Specific server
```

### Ping All

```bash
cm ping
```

Pings every server and node, shows online/offline status.

### Compare Servers

```bash
cm compare
```

Side-by-side comparison of all servers: CPU, RAM, disk.

---

## 8. Running Commands Remotely

### Run on All Servers

```bash
cm run "apt update && apt upgrade -y"
```

Executes the command via SSH on every registered server.

### Run on Specific Servers

```bash
cm run "docker ps" -s "web-1,web-2"
```

### Run on Best Server

```bash
cm run "python train.py" --best
```

Picks the server with the most free RAM/CPU.

### Run on Node

```bash
cm node exec -n NAME "uptime"
# Alias: cm exec
```

Executes via the TCP node agent (faster than SSH).

### Batch Execute on All Nodes (v2.0.0)

```bash
cm exec --all "uptime"
```

Runs the command on every connected node at once.

### Distribution Plan

```bash
cm plan "deploy.sh"
```

Shows which server would run what based on resource availability, without actually executing.

### Task Slicing

```bash
cm slice --file data.csv --parts 4
```

Auto-slices a file across servers based on available resources.

---

## 9. File Operations

### Upload/Download

```bash
# Upload a file
cm transfer -s SERVER -l /local/path -r /remote/path

# Download a file
cm transfer -s SERVER -l /local/path -r /remote/path --download

# Alias: cm cp
```

Uses SFTP under the hood (via paramiko). Supports large files.

### Directory Sync

```bash
cm sync -s SERVER -l /local/dir -r /remote/dir
```

Compares MD5 checksums and only transfers changed files.

### Auto-sync

```bash
cm autosync -s SERVER -l /local/dir -r /remote/dir -i 300
```

Watches a local directory and syncs to server every N seconds.

### Search Files

```bash
cm find -n NAME -p /path -q "pattern"
# Alias: cm find
```

Runs `find` on the remote server with name pattern matching.

### Backups

```bash
cm backup list              # List backups
cm backup create -n NAME    # Create backup
cm backup restore -n NAME   # Restore backup
```

---

## 10. Docker Management

All Docker commands work on servers connected via SSH.

### List Servers with Docker

```bash
cm docker list-servers
```

### List Containers

```bash
cm docker containers -s SERVER
# Alias: cm dcls
```

Shows: Container ID, Name, Image, Status, Ports.

### Container Stats

```bash
cm docker stats -s SERVER
# Alias: cm dcstats
```

Shows CPU%, Memory, Network I/O for each container.

### Exec in Container

```bash
cm docker exec CONTAINER "ls -la" -s SERVER
# Alias: cm dcexec
```

### Container Logs

```bash
cm docker logs CONTAINER -s SERVER
# Alias: cm dclogs
```

### List Images

```bash
cm docker images -s SERVER
```

### Pull Image

```bash
cm docker pull nginx -s SERVER
```

### Docker Compose

```bash
cm docker compose /path/to/docker-compose.yml -s SERVER
```

Runs `docker-compose up -d` on the remote server.

### Cleanup

```bash
cm docker cleanup -s SERVER
```

Removes stopped containers, unused networks, dangling images.

### Prune Everything

```bash
cm docker prune -s SERVER
```

Aggressive cleanup: removes all unused containers, networks, images, build cache.

---

## 11. Firewall Management

### Check Status

```bash
cm firewall status
# Alias: cm fw
```

Auto-detects whether the server uses `ufw` or `iptables`.

### Add Rule

```bash
cm firewall add-rule --port 443 --proto tcp --action allow
# Alias: cm fwadd
```

**Parameters:**
- `--port`: Port number
- `--proto`: Protocol (tcp/udp)
- `--action`: allow/deny/reject

**Examples:**
```bash
cm fwadd --port 80 --proto tcp --action allow
cm fwadd --port 3306 --proto tcp --action deny
```

### Remove Rule

```bash
cm firewall remove-rule --port 443
```

### List Rules

```bash
cm firewall list-rules
```

### Check if Port is Open

```bash
cm firewall check-port --port 443
```

### Backup Rules

```bash
cm firewall backup -s SERVER
```

### Load Rules from File

```bash
cm firewall load -f rules.txt -s SERVER
```

---

## 12. SSL Certificate Monitoring

### Check a Domain

```bash
cm ssl check example.com
# Alias: cm sslchk example.com
```

Shows: issuer, subject, SANs, expiry date, days remaining, warning if < 30 days.

### Check All Domains

```bash
cm ssl check-all
# Alias: cm sslall
```

Checks every domain in your watch list.

### Add Domain to Watch List

```bash
cm ssl add example.com
```

### Remove Domain

```bash
cm ssl remove example.com
```

### List Watched Domains

```bash
cm ssl domains
```

### Expiry History

```bash
cm ssl history
```

### Check Renewal Status

```bash
cm ssl renew-check
```

---

## 13. Log Aggregation

### Read Logs

```bash
cm logs -n NAME
# Alias: cm log -n NAME
```

Reads `/var/log/syslog` (or `/var/log/messages` on some distros).

### Search Logs

```bash
cm logagg search -p "error" -s SERVER
# Alias: cm logsearch -p "error"
```

### Filter by Severity

```bash
cm logagg filter -l ERROR -s SERVER
```

### Tail Logs Live

```bash
cm logagg subscribe -s SERVER
```

### List Log Sources

```bash
cm logagg sources
```

### Add Custom Log Source

```bash
cm logagg add-source --name "nginx" --path /var/log/nginx/access.log
```

### Log Statistics

```bash
cm logagg stats -s SERVER
```

### Clear Log Index

```bash
cm logagg clear
```

---

## 14. Webhooks & Alerts

Webhooks send notifications to external services when events happen.

### Supported Types

- **Discord**: Sends to a Discord webhook URL
- **Telegram**: Sends to a Telegram bot
- **Custom**: Sends raw HTTP POST to any URL

### Add Webhook

```bash
cm webhooks add --name alerts --url https://discord.com/api/webhooks/XXX --type discord
```

### Send Message

```bash
cm webhooks send "Server is down!" --event error
# Alias: cm whsend "Server is down!"
```

### Test Webhook

```bash
cm webhooks test -n alerts
```

### List Webhooks

```bash
cm webhooks list
```

### Webhook Log

```bash
cm webhooks log
```

### Enable/Disable All

```bash
cm webhooks enable-all
cm webhooks disable-all
```

### Remove Webhook

```bash
cm webhooks remove --name alerts
```

---

## 15. Process Watchers

Watchers monitor whether a specific process is running on a server. If it stops (or starts), you get alerted.

### Add Watcher

```bash
cm watcher add --name nginx-watch --process nginx --server web-1 --alert-on stop
```

**Parameters:**
- `--name`: Watcher name
- `--process`: Process name to watch
- `--server`: Server to monitor (optional, monitors all if omitted)
- `--alert-on`: "stop" (alert when process stops) or "start" (alert when it starts)

### Check All Watchers

```bash
cm watcher check
# Alias: cm wtchk
```

### Check Specific Process

```bash
cm watcher check-status --process nginx -s web-1
```

### List Watchers

```bash
cm watcher list
```

### Watcher Alerts

```bash
cm watcher alerts
```

### Remove Watcher

```bash
cm watcher remove --name nginx-watch
```

---

## 16. ACL (Access Control)

The ACL system controls who can use CloudMesh. It supports multiple users with different roles.

### Default Roles

- **admin**: Full access to everything
- **viewer**: Can only run `monitor`, `ping`, `list`, `info`

### Add User

```bash
cm acl add-user -u john -p mypassword -r admin
# Alias: cm acladd
```

### List Users

```bash
cm acl users
# Alias: cm aclu
```

### Remove User

```bash
cm acl remove-user -u john
# Alias: cm aclrm
```

### Set Role

```bash
cm acl set-role -u john -r viewer
```

### Enable/Disable User

```bash
cm acl enable -u john
cm acl disable -u john
```

### List Roles

```bash
cm acl roles
```

### Add Custom Role

```bash
cm acl add-role -r custom-role
```

### Remove Role

```bash
cm acl remove-role -r custom-role
```

---

## 17. SSH Tunnels

SSH tunnels let you forward a local port to a remote server through an SSH connection.

### Add Tunnel

```bash
cm tunnel add --name db-tunnel --host 10.0.0.5 -l 3306 -r 3306
# Alias: cm tunadd
```

**Parameters:**
- `--name`: Tunnel name
- `--host`: Remote host
- `-l / --local-port`: Local port to listen on
- `-r / --remote-port`: Remote port to forward to

### Start Tunnel

```bash
cm tunnel start -n db-tunnel
# Alias: cm tunstart
```

### Stop Tunnel

```bash
cm tunnel stop -n db-tunnel
# Alias: cm tunstop
```

### Quick Tunnel

```bash
cm tunnel quick --host 10.0.0.5 -l 5432 -r 5432
```

Creates and starts a tunnel in one command.

### List Tunnels

```bash
cm tunnel list
```

### Tunnel Status

```bash
cm tunnel status
```

### Stop All Tunnels

```bash
cm tunnel stop-all
```

---

## 18. Database Management

Supports MySQL and PostgreSQL via SSH.

### Database Status

```bash
cm database status -s SERVER -t mysql -P rootpassword
# Alias: cm dbstatus
```

### Run Query

```bash
cm database query -s SERVER -t mysql -P PASSWORD "SHOW PROCESSLIST"
# Alias: cm dbq -s SERVER -t mysql -P PASSWORD "SHOW PROCESSLIST"
```

### Backup Database

```bash
cm database backup -s SERVER -t mysql -P PASSWORD -d myapp
# Alias: cm dbbak
```

### List Databases

```bash
cm database list -s SERVER -t mysql -P PASSWORD
```

**Security note:** Passwords are written to a temp file on the remote server, used for the query, then immediately deleted.

---

## 19. Scheduling

Schedule recurring commands to run automatically.

### Add Schedule

```bash
cm schedule add -n monitor "cm ping" -i 300
```

**Parameters:**
- `-n / --name`: Schedule name
- Command to run
- `-i / --interval`: Interval in seconds

**Examples:**
```bash
cm schedule add -n health "cm mon --local" -i 60       # Every minute
cm schedule add -n cleanup "cm cleanup" -i 86400        # Daily
cm schedule add -n check "cm ssl check-all" -i 3600     # Hourly
```

### List Schedules

```bash
cm schedule list
```

### Remove Schedule

```bash
cm schedule remove -n monitor
```

### Toggle Schedule

```bash
cm schedule toggle -n monitor
```

Enables/disables the schedule without deleting it.

---

## 20. Notifications

### Setup Telegram Bot

```bash
cm notify setup-telegram --token BOT_TOKEN --chat-id CHAT_ID
```

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Get your chat ID (send a message to the bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates`)
3. Run the command above

### Setup Discord Webhook

```bash
cm notify setup-discord --webhook WEBHOOK_URL
```

1. Go to your Discord server settings > Integrations > Webhooks
2. Create a webhook, copy the URL
3. Run the command above

### Send Notification

```bash
cm notify send "Server disk is 90% full!"
```

Sends to all configured notification channels.

### Notification Status

```bash
cm notify status
```

---

## 21. Plugins System

Plugins are named shell commands stored in a JSON registry. They can run locally or remotely on all servers.

### Plugin Format

```json
{
  "plugin-name": {
    "command": "df -h | head -5",
    "description": "Show disk usage summary",
    "targets": "all"
  }
}
```

**Fields:**
- `command` (required): The shell command to execute
- `description` (optional): What the plugin does
- `targets`: `"all"` (run on all servers via SSH) or `"local"` (run on your machine)

### Add Plugin

```bash
cm plugins add --name diskcheck --command "df -h | head -5" --desc "Disk usage" --targets all
```

### List Plugins

```bash
cm plugins list
```

### Run Plugin

```bash
cm plugins run --name diskcheck

# Run on specific server
cm plugins run --name diskcheck --server web-1

# Shortcut
cm pluginrun -n diskcheck
```

### Remove Plugin

```bash
cm plugins remove --name diskcheck
```

### Export Plugin (Share with others)

```bash
cm plugins export --name diskcheck -o diskcheck_plugin.json
```

Creates a JSON file that can be imported by anyone.

### Import Plugin

```bash
cm plugins import diskcheck_plugin.json
```

Merges the plugin into your registry. Overwrites if same name exists.

### Creating Your Own Plugins

**Example 1: System info plugin**
```bash
cm plugins add --name sysinfo \
  --command "echo 'Hostname:' $(hostname) && echo 'Uptime:' $(uptime -p) && echo 'Load:' $(cat /proc/loadavg | cut -d' ' -f1-3)" \
  --desc "Quick system info" \
  --targets all
```

**Example 2: Docker health plugin**
```bash
cm plugins add --name docker-health \
  --command "docker ps --format '{{.Names}}: {{.Status}}' | head -10" \
  --desc "Docker container status" \
  --targets all
```

**Example 3: Local plugin**
```bash
cm plugins add --name myip \
  --command "curl -s ifconfig.me" \
  --desc "Get public IP" \
  --targets local
```

**Example 4: Backup plugin**
```bash
cm plugins add --name db-backup \
  --command "mysqldump -u root -pPASSWORD mydb | gzip > /backups/mydb_$(date +%Y%m%d).sql.gz" \
  --desc "Backup MySQL database" \
  --targets all
```

**Example 5: SSL expiry checker**
```bash
cm plugins add --name ssl-check \
  --command "echo | openssl s_client -connect example.com:443 2>/dev/null | openssl x509 -noout -dates" \
  --desc "Check SSL expiry" \
  --targets all
```

### Sharing Plugins

1. Export: `cm plugins export --name myplugin -o share/myplugin.json`
2. Share the JSON file
3. Recipient imports: `cm plugins import share/myplugin.json`

**SECURITY WARNING:** Plugins execute arbitrary commands. Only import plugins from people you trust. Never import plugins from untrusted sources.

---

## 22. SSH Key Management

### Generate Key Pair

```bash
cm keys generate
```

Creates a new SSH key pair in `~/.ssh/cm_keys`.

### List Keys

```bash
cm keys list
```

### Show Public Key

```bash
cm keys show
```

### Deploy to All Servers

```bash
cm keys deploy
```

Copies your public key to all registered servers.

### Remove Managed Key

```bash
cm keys remove-managed
```

---

## 23. Configuration Management

### List Config Files

```bash
cm config list
```

Shows all config files and their locations.

### Export Config

```bash
cm config export -d /backup/dir
```

Exports all config files to a directory.

### Import Config

```bash
cm config import -d /backup/dir
```

Imports config from a directory.

### Show Config Contents

```bash
cm config show
```

### Profiles

Profiles let you save and switch between different configurations.

```bash
cm profile save -n production     # Save current config as "production"
cm profile load -n production     # Load the "production" profile
cm profile list                   # List all profiles
cm profile delete -n production   # Delete a profile
```

---

## 24. Shell Completions

Enable tab completion for CloudMesh commands in your shell.

### Bash

```bash
cm completions bash >> ~/.bashrc
source ~/.bashrc
```

### Zsh

```bash
cm completions zsh >> ~/.zshrc
source ~/.zshrc
```

### PowerShell

```powershell
cm completions powershell >> $PROFILE
. $PROFILE
```

After enabling, type `cm ` and press TAB to see all available commands.

---

## 25. Security Features

CloudMesh has extensive security built in:

### API Authentication

The REST API requires an `X-Api-Key` header on every request:

```bash
cm api --port 8080
# Prints the API key

curl -H "X-Api-Key: YOUR_KEY" http://127.0.0.1:8080/api/status
```

### Node Auth Keys

Each node has a unique auth key. The controller authenticates using HMAC comparison:

```python
# The node verifies:
hmac.compare_digest(received_key, stored_key)
```

### File Encryption

All config is encrypted using Fernet symmetric encryption:

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()        # Auto-generated, stored in .secret.key
encrypted = fernet.encrypt(data)   # Encrypt config
decrypted = fernet.decrypt(data)   # Decrypt config
```

### SSH Policy

CloudMesh uses `RejectPolicy` for unknown hosts — no silent acceptance of host keys:

```python
# If host key is not in known_hosts, connection is REJECTED
# You must manually add the host:
ssh-keyscan -H SERVER_IP >> ~/.ssh/known_hosts
```

### Host Key Verification

Default `StrictHostKeyChecking=yes`. If you disable it, you get a warning:

```
WARNING: StrictHostKeyChecking disabled for 192.168.1.100.
This connection is vulnerable to MITM attacks.
Add the host key with: ssh-keyscan 192.168.1.100 >> ~/.ssh/known_hosts
```

### Path Traversal Protection

File operations on nodes use `shlex.quote()` to prevent path injection:

```python
safe_path = shlex.quote(user_input)  # Prevents: ../../../etc/passwd
```

### TLS Support

Nodes can optionally use TLS encryption:

```bash
cm node start --tls-cert cert.pem --tls-key key.pem
```

### ACL System

Role-based access control with admin/viewer/custom roles. Users authenticate with password (SHA-256 + salt).

### Key Rotation

You can rotate all keys at any time:

```bash
cm panic              # Rotate everything (local + remote)
cm panic --dry-run    # Preview what would happen
```

---

## 26. Ghost Ports (SPA)

**SPA = Single Packet Authorization.** This makes your TCP port invisible to port scanners.

### How It Works

1. Node listens on a **UDP port** (default 9998) silently
2. Controller sends a signed HMAC packet (the "knock") to the UDP port
3. Node validates the HMAC signature
4. If valid, node opens the **TCP port** for N seconds (default 5)
5. Controller connects to the TCP port within that window
6. After N seconds, TCP port closes automatically
7. Port scanners see nothing — UDP listening is invisible to TCP scanners

### Starting with SPA

```bash
# On the node:
cm node start --spa

# Custom options:
cm node start --spa --spa-port 9998    # Custom UDP port
cm node start --spa --spa-window 10    # TCP stays open 10s
```

### Source IP Binding

The iptables ACCEPT rule uses `-s <source_ip>`, meaning **only the knocker's IP** can connect during the window. Even if someone sniffed the SPA packet, they could not connect from a different IP.

### Fail-Closed

If the iptables DROP rule fails to apply at startup, the node **refuses to start**. This prevents the TCP port from being exposed without protection.

### Sending a Knock

The knock is sent automatically by `NodeClient`:

```python
NodeClient.send_spa_knock(host, auth_key, spa_port=9998)
```

---

## 27. Tripwire Keys

Tripwire keys are **decoy keys** placed on honeypot servers. If anyone tries to use a tripwire key, you get an immediate alert.

### Plant a Tripwire

```bash
cm tripwire plant --node honeypot --host 10.0.0.99
# Aliases: cm tw plant, cm triw plant
```

This generates a fake key and saves it as a tripwire. If anyone authenticates with this key, it triggers an alert.

### List Tripwires

```bash
cm tripwire list
# Aliases: cm tw list, cm triw list
```

### Check if Triggered

```bash
cm tripwire check
# Aliases: cm tw check, cm triw check
```

### Remove Tripwire

```bash
cm tripwire remove --node honeypot
# Aliases: cm tw remove, cm triw remove
```

---

## 28. Emergency Panic Button

The panic button rotates ALL encryption keys and node auth keys instantly.

### What It Does

1. Generates a new Fernet encryption key
2. Overwrites `.secret.key` (backs up the old one)
3. Generates new auth keys for every node
4. Sends `rotate_key` to each remote node (updates their keys too)
5. Logs the event in `.panic_log.json`
6. If a node is offline, rotation is saved to `.panic_pending.json` for retry

### Dry Run (Preview)

```bash
cm panic --dry-run
```

Shows what would happen without making any changes.

### Execute Panic

```bash
cm panic
```

Rotates everything immediately. After this, you must re-add nodes with new auth keys.

### What Gets Rotated

- `.secret.key` — Fernet encryption key (backup: `.secret.key.bak`)
- `.node_keys.json` — All node auth keys (backup: `.node_keys.json.bak`)
- Remote nodes — Each node's auth key is updated via `rotate_key` action

---

## 29. Shamir Panic

Instead of a single panic key, you can split it into 3 shares using Shamir's Secret Sharing. You need 2 of 3 shares to execute panic.

### Setup

```bash
cm panic setup
```

Generates 3 shares and displays them. **Write them down and store each on a separate device.**

### View Shares Status

```bash
cm panic shares
```

Shows when shares were created and threshold info.

### Execute with Shares

```bash
cm panic execute --share 1 --share 2
```

Provide at least 2 share IDs to execute panic.

### How It Works

The panic key is split into 3 shares using Shamir's Secret Sharing over GF(p) (Galois Field with prime modulus). Any 2 shares can reconstruct the key. A single compromised device cannot trigger panic alone.

---

## 30. Remote Panic Rotation

### Rotate Keys on All Remote Nodes

```bash
cm panic rotate
```

Connects to each node and calls `rotate_key` with a new auth key.

### Retry Failed Rotations

```bash
cm panic retry-pending
```

If some nodes were offline during `cm panic`, their rotations are saved to `.panic_pending.json`. When they come back online, run this command to retry.

---

## 31. Resource Weather Forecast

The weather system records CPU/RAM snapshots and predicts future resource usage.

### Learn (Record Data)

```bash
cm weather --learn
```

Records current CPU and RAM for all servers. Run this periodically (e.g., via cron or `cm schedule`) to build the forecast model.

### Predict

```bash
cm weather                    # Predict for next hour
cm weather -s prod-server     # Predict for specific server
```

### Clear Data

```bash
cm weather --clear
```

### How It Works

Uses Exponential Moving Average (EMA) with alpha=0.3. Each hour has its own EMA values for CPU and RAM. As you collect more samples, the predictions become more accurate.

---

## 32. Distributed Trust

The gossip protocol evaluates node trustworthiness by comparing controller observations vs node self-reports.

### Scan Nodes

```bash
cm trust --scan
```

1. Controller pings each node (measures reachability + latency)
2. Asks each node to self-report its metrics
3. Compares controller observation vs self-report
4. Calculates trust score (0-100)

### View Trust Status

```bash
cm trust
```

Shows trust scores for all nodes. Suspicious nodes (trust < 50) are flagged.

### How It Works

- Controller records its own observations (reachable? latency?)
- Node reports its own state (healthy? metrics?)
- If they disagree significantly, trust score drops
- Trust score starts at 100 and decreases with each discrepancy
- History is limited to 60 entries per node

---

## 33. Job Checkpointing

Long-running jobs can be checkpointed so they survive node crashes.

### Checkpoint a Job

```bash
cm node job checkpoint -n gpu-1 -j JOB_ID
```

Saves the job's current state to disk.

### List Checkpoints

```bash
cm node job checkpoints
```

### Recover Jobs

```bash
cm node job recover                  # List recoverable jobs
cm node job recover --relaunch       # Auto-relaunch all recoverable jobs
```

### Start Async Job

```bash
cm node job start -n gpu-1 "python train.py"
# Alias: cm js -n gpu-1 "python train.py"
```

### Check Job Status

```bash
cm node job status -n gpu-1 -j JOB_ID
```

### List Jobs

```bash
cm node job list -n gpu-1
```

### Kill Job

```bash
cm node job kill -n gpu-1 -j JOB_ID
```

---

## 34. Command Ledger (Tamper Detection)

Every command you run through CloudMesh is logged with a SHA-256 hash chain. Any tampering breaks the chain.

### Verify Chain Integrity

```bash
cm cmdlog --verify
```

**Output examples:**
```
Chain intact — all 42 entries verified.
Chain BROKEN at entry #17 — possible tampering detected.
```

### How It Works

Each entry contains:
- `timestamp`: When the command was run
- `command`: What was executed
- `args`: Arguments
- `prev_hash`: Hash of the previous entry
- `entry_hash`: SHA-256 of (prev_hash + timestamp + command + args)

If anyone modifies a past entry, the hash chain breaks and verification fails.

---

## 35. DDoS Protection

The REST API has built-in DDoS protection with multiple layers:

### Rate Limiting

- Max 30 requests per minute per IP
- Uses sliding window algorithm

### Connection Limits

- Max 5 concurrent connections per IP
- Max 100 total concurrent connections

### IP Auto-Banning

- After 5 failed authentication attempts, IP is banned for 5 minutes
- Ban list persists across restarts (stored in `data/banned_ips.json`)

### Packet Validation

- Max packet size: 1 MB
- Min packet size: 10 bytes
- Must be valid JSON with an `action` field
- Max JSON depth: 5 levels

### Slowloris Guard

- Clients must send their header within 10 seconds
- Rejects packets > 50 MB (absurd size)
- Prevents slow-header attacks that tie up connections

### How It Works

All defenses are composed in the `DDoSProtection` class:

```python
DDoSProtection(
    rate_max=30,         # requests per window
    rate_window=60,      # window in seconds
    conn_per_ip=5,       # max connections per IP
    conn_total=100,      # max total connections
    ban_threshold=5,     # failures before ban
    ban_duration=300,    # ban duration in seconds
    read_timeout=10,     # slowloris timeout
)
```

---

## 36. Self Update

```bash
cm update
```

Checks GitHub for the latest release, downloads it, and updates the local installation.

---

## 37. Doctor (Health Check)

```bash
cm doctor
```

Runs 15 health checks:

1. Python version check
2. Required packages installed
3. Config file exists
4. Encryption key exists
5. Server configs valid
6. Node keys exist
7. SSH client available
8. Network connectivity
9. Firewall status
10. TLS configuration
11. SPA configuration
12. Plugin safety
13. ACL status
14. Command ledger integrity
15. Disk space check

---

## 38. Network Discovery

```bash
cm discover 192.168.1
```

Scans a /24 subnet (192.168.1.1 to 192.168.1.254) for hosts running the CloudMesh node agent on port 9999.

Uses 50 concurrent threads for fast scanning.

### Custom Port

```bash
cm discover 192.168.1 --port 8080
```

---

## 39. Benchmarks

```bash
cm bench -s SERVER
```

Runs CPU, disk, and RAM benchmarks on a remote server.

### What It Measures

- **CPU**: MD5 hashing operations per second
- **Disk**: Write/read throughput in MB/s (10 MB test file)
- **RAM**: Memory allocation and access speed (64 MB test)

---

## 40. Security Audits

```bash
cm audit -n NAME
```

Runs 8 security checks on a server:

1. Root SSH login enabled?
2. Firewall active?
3. Open ports
4. Failed login attempts
5. Shell users
6. LUKS encryption
7. Auto-updates enabled
8. Public key authentication

Each check is tagged as low/medium/high/unknown risk.

---

## 41. REST API

```bash
cm api --port 8080
```

Starts a threaded HTTP server on 127.0.0.1 with API key authentication.

### Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | System status |
| `/api/health` | GET | Health check |
| `/api/servers` | GET | List servers |
| `/api/nodes` | GET | List nodes |
| `/api/exec/<server>` | POST | Execute command |
| `/api/acl/users` | GET | List users |
| `/api/acl/roles` | GET | List roles |

### Example

```bash
# Start API
cm api --port 8080

# Use it
curl -H "X-Api-Key: YOUR_KEY" http://127.0.0.1:8080/api/status
curl -H "X-Api-Key: YOUR_KEY" http://127.0.0.1:8080/api/servers
```

### Dangerous Command Blocklist

The `/api/exec` endpoint blocks dangerous commands: `rm -rf`, `mkfs`, `dd`, `:(){ :|:& };:`, etc.

---

## 42. Interactive TUI

```bash
cm interactive
```

Opens a text-based user interface with menus for all major features. Navigate with arrow keys and Enter.

---

## 43. Aliases

Create short aliases for long commands.

### Add Alias

```bash
cm alias add -n myalias -c "run 'apt update'"
```

### Use Alias

```bash
cm myalias
```

### List Aliases

```bash
cm alias list
```

### Remove Alias

```bash
cm alias remove -n myalias
```

---

## 44. Templates

Templates are reusable command patterns with placeholders.

### Add Template

```bash
cm template add -n deploy -c "ssh {host} 'cd /app && git pull && systemctl restart {service}'"
```

### Run Template

```bash
cm template run -n deploy --host web-1 --service nginx
```

### List Templates

```bash
cm template list
```

### Remove Template

```bash
cm template remove -n deploy
```

---

## 45. Profiles

Save and switch between different configurations.

```bash
cm profile save -n production       # Save current config
cm profile load -n production       # Load profile
cm profile list                     # List all profiles
cm profile delete -n production     # Delete profile
```

---

## 46. Resource History

Record resource snapshots over time.

```bash
cm reshistory snapshot              # Take snapshot
cm reshistory show                  # Show history
cm reshistory summary               # Summary
cm reshistory clear                 # Clear history
```

---

## 47. Device Groups

Group servers and nodes for batch operations.

```bash
cm group create -n webservers                # Create group
cm group add -n webservers -d web-1          # Add device
cm group add -n webservers -d web-2          # Add device
cm group list                                # List groups
cm group run -n webservers "uptime"          # Run on group
cm group remove -n webservers -d web-1       # Remove device
cm group delete -n webservers                # Delete group
```

---

## 48. Service Management

Run CloudMesh as a background service.

```bash
cm service start              # Start service
cm service stop               # Stop service
cm service status             # Check status
cm service logs               # View logs
```

---

## 49. GPU Telemetry

Monitor GPU usage on nodes with NVIDIA GPUs.

```bash
cm node gpu -n NAME
# Alias: cm gpunode
```

Shows: GPU name, utilization %, memory used/total, temperature, power draw.

Requires `nvidia-smi` on the remote node.

---

## 50. Project Structure

```
cloudmesh/
  main.py              # CLI entry point (155+ commands)
  requirements.txt     # Python dependencies
  core/
    server.py          # SSH server management (ServerManager class)
    monitor.py         # Resource monitoring (ResourceMonitor class)
    transfer.py        # File transfer via SFTP (FileTransfer class)
    sync.py            # Directory sync with MD5 (DirectorySync class)
    deploy.py          # Package deployment
    alerts.py          # Threshold alerts (AlertManager class)
    groups.py          # Device groups (GroupsManager class)
    tui.py             # Interactive TUI (Textual-based)
    docker.py          # Docker management (functions)
    firewall.py        # Firewall management (ufw/iptables)
    sslcheck.py        # SSL certificate monitoring
    logagg.py          # Log aggregation
    acl.py             # Multi-user ACL (functions)
    webhooks.py        # Webhook integrations (Discord/Telegram/custom)
    watcher.py         # Process watcher
    database.py        # Database management (MySQL/PostgreSQL)
    cmdlog.py          # Immutable command ledger (SHA-256 hash chain)
    security.py        # Fernet encryption (SecurityManager class)
    service.py         # Systemd service management
    gpu.py             # GPU telemetry via nvidia-smi
    jobs.py            # Async job system
    node_client.py     # TCP node communication (NodeClient class)
    ssh_util.py        # Centralized SSH with host key verification
    features.py        # 20 utility features (functions)
    advanced.py        # 10 advanced features (classes)
    ddos.py            # DDoS protection (6 defense classes)
    panic.py           # Emergency key rotation (PanicManager class)
    weather.py         # Resource weather forecast (WeatherForecast class)
    gossip.py          # Distributed trust (GossipManager class)
    checkpoint.py      # Job checkpoint manager
    shamir.py          # Shamir Secret Sharing over GF(p)
    tunnels.py         # SSH tunnel manager
    cost.py            # Cost estimator
    reshistory.py      # Resource history
    dashboard.py       # Live dashboard
    history.py         # Command history
    plugins.py         # Plugin system (functions)
  node/
    cloudmesh_node.py  # Standalone node agent (SPA, DDoS, TLS)
  tests/
    test_security.py   # 58 security tests
  data/                # Auto-created config/state files
```

---

## 51. Contributing

### Development Setup

```bash
git clone https://github.com/MrAli88708/CloudMesh.git
cd CloudMesh
python -m venv venv
source venv/bin/activate  # Linux
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### Running Tests

```bash
python -m pytest cloudmesh/tests/test_security.py -v
```

### Code Style

- Pure Python, no frameworks
- Rich library for terminal UI
- Paramiko for SSH
- psutil for system monitoring
- All config stored as JSON
- Sensitive data encrypted with Fernet

### Adding a New Command

1. Add the function in `cloudmesh/main.py`
2. Register the subparser in the `main()` function
3. Add dispatch in the `cmds` dict at the bottom
4. Add tests in `cloudmesh/tests/test_security.py`

### Adding a New Core Module

1. Create the file in `cloudmesh/core/`
2. Import it in `main.py`
3. Wire it up to a CLI command
4. Add tests

---

<div align="center">

**Created and Developed by MRSX PRO**

**GitHub:** [MrAli88708](https://github.com/MrAli88708)

**Repository:** [CloudMesh](https://github.com/MrAli88708/CloudMesh)

All rights reserved. This project is maintained by **MRSX PRO**.

</div>
