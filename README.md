<div align="center">

# CloudMesh

### One Console to Control Them All

Connect multiple devices and servers into one unified resource pool.
Monitor, manage, and distribute workloads from a single terminal.

#### Made By MRSX

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-blue?style=for-the-badge)]()
[![Commands](https://img.shields.io/badge/Commands-130+-orange?style=for-the-badge)]()
[![Stars](https://img.shields.io/github/stars/MrAli88708/CloudMesh?style=for-the-badge&color=yellow)](https://github.com/MrAli88708/CloudMesh/stargazers)
[![Security](https://img.shields.io/badge/Security-Secured-red?style=for-the-badge)]()

<br>

```
  __  __           _        ____
 |  \/  | ___  ___| |__    / ___|___  _ __ ___
 | |\/| |/ _ \/ __| '_ \  | |   / _ \| '__/ _ \
 | |  | |  __/\__ \ | | | | |__| (_) | | |  __/
 |_|  |_|\___||___/_| |_|  \____\___/|_|  \___|

```

**130+ commands** | **Auto-discovery** | **Real-time monitoring** | **GPU telemetry** | **API auth**

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
| Docker scattered across servers | `cm docker` - manage containers on any node |
| No cost awareness | `cm cost` - estimate and compare cloud pricing |

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
cm --help              # See all 130+ commands
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
<summary><b>Docker Management</b></summary>

| Command | Description |
|---------|-------------|
| `cm docker list-servers` | List servers with Docker |
| `cm docker containers` | List containers on server |
| `cm docker compose` | Run docker-compose on server |
| `cm docker stats` | Container resource stats |
| `cm docker images` | List Docker images |
| `cm docker pull` | Pull image on server |
| `cm docker exec` | Exec command in container |
| `cm docker logs` | Container logs |
| `cm docker cleanup` | Cleanup Docker resources |
| `cm docker prune` | Prune everything |

</details>

<details>
<summary><b>Firewall Manager</b></summary>

| Command | Description |
|---------|-------------|
| `cm firewall list-rules` | List firewall rules |
| `cm firewall add-rule` | Add firewall rule |
| `cm firewall remove-rule` | Remove firewall rule |
| `cm firewall status` | Firewall status |
| `cm firewall check-port` | Check if port is open |
| `cm firewall backup` | Backup rules to file |
| `cm firewall load` | Load rules from file |

</details>

<details>
<summary><b>SSL Certificate Monitor</b></summary>

| Command | Description |
|---------|-------------|
| `cm ssl check` | Check SSL certificate |
| `cm ssl check-all` | Check all domains |
| `cm ssl domains` | List monitored domains |
| `cm ssl add` | Add domain to monitor |
| `cm ssl remove` | Remove domain |
| `cm ssl history` | Expiry check history |
| `cm ssl renew-check` | Check renewal status |

</details>

<details>
<summary><b>Log Aggregation</b></summary>

| Command | Description |
|---------|-------------|
| `cm logagg add-source` | Add log source |
| `cm logagg sources` | List log sources |
| `cm logagg search` | Search logs by pattern |
| `cm logagg filter` | Filter by level |
| `cm logagg subscribe` | Tail logs live |
| `cm logagg stats` | Log statistics |
| `cm logagg clear` | Clear log index |

</details>

<details>
<summary><b>Resource History</b></summary>

| Command | Description |
|---------|-------------|
| `cm reshistory snapshot` | Take resource snapshot |
| `cm reshistory show` | Show history for server |
| `cm reshistory summary` | Stats summary |
| `cm reshistory clear` | Clear history |

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
<summary><b>Custom Plugins</b></summary>

| Command | Description |
|---------|-------------|
| `cm plugins list` | List installed plugins |
| `cm plugins add` | Add custom plugin |
| `cm plugins remove` | Remove plugin |
| `cm plugins run` | Run plugin on servers |
| `cm plugins import` | Import plugins from file |
| `cm plugins export` | Export plugin to file |

</details>

<details>
<summary><b>Multi-User ACL</b></summary>

| Command | Description |
|---------|-------------|
| `cm acl users` | List users |
| `cm acl add-user` | Add user with role |
| `cm acl remove-user` | Remove user |
| `cm acl set-role` | Change user role |
| `cm acl enable` | Enable user |
| `cm acl disable` | Disable user |
| `cm acl roles` | List roles & permissions |
| `cm acl add-role` | Create role |
| `cm acl remove-role` | Delete role |

</details>

<details>
<summary><b>Webhook Integrations</b></summary>

| Command | Description |
|---------|-------------|
| `cm webhooks list` | List webhooks |
| `cm webhooks add` | Add Discord/Slack/Telegram/custom |
| `cm webhooks remove` | Remove webhook |
| `cm webhooks test` | Test webhook |
| `cm webhooks log` | Webhook delivery log |
| `cm webhooks send` | Send custom message |

</details>

<details>
<summary><b>Process Watcher</b></summary>

| Command | Description |
|---------|-------------|
| `cm watcher list` | List watchers |
| `cm watcher add` | Watch process on server |
| `cm watcher remove` | Remove watcher |
| `cm watcher check` | Check all watchers |
| `cm watcher check-status` | Check process on server |
| `cm watcher alerts` | View watcher alerts |

</details>

<details>
<summary><b>Cost Estimator</b></summary>

| Command | Description |
|---------|-------------|
| `cm cost instances` | List instance prices |
| `cm cost estimate` | Estimate cost |
| `cm cost compare` | Compare across providers |
| `cm cost cheapest` | Find cheapest option |

Supports: AWS, GCP, Azure, DigitalOcean

</details>

<details>
<summary><b>SSH Tunnel Manager</b></summary>

| Command | Description |
|---------|-------------|
| `cm tunnel list` | List tunnels |
| `cm tunnel add` | Add tunnel |
| `cm tunnel remove` | Remove tunnel |
| `cm tunnel start` | Start tunnel |
| `cm tunnel stop` | Stop tunnel |
| `cm tunnel stop-all` | Stop all tunnels |
| `cm tunnel status` | Tunnel status |
| `cm tunnel quick` | Quick one-liner tunnel |

</details>

<details>
<summary><b>Database Manager</b></summary>

| Command | Description |
|---------|-------------|
| `cm database list` | List databases |
| `cm database status` | Database status |
| `cm database query` | Run SQL query |
| `cm database backup` | Backup database |

Supports: MySQL, PostgreSQL

</details>

<details>
<summary><b>Advanced Features</b></summary>

| Command | Description |
|---------|-------------|
| `cm bench` | CPU/RAM/Disk benchmark |
| `cm schedule` | Recurring commands |
| `cm notify` | Telegram/Discord alerts |
| `cm api` | REST API (auth required) |
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

## Quick Reference

### Server Management
| Command | Alias | Description |
|---------|-------|-------------|
| `cm server add -n NAME -H HOST -u USER` | `cm add` | Add server via SSH |
| `cm server remove -n NAME` | `cm rm` | Remove server |
| `cm server list` | `cm ls` | List all servers |
| `cm server test -n NAME` | `cm test` | Test connection |
| `cm server info -n NAME` | `cm info` | Server details |
| `cm run "cmd"` | `cm run` | Run on all servers |

### Monitoring
| Command | Alias | Description |
|---------|-------|-------------|
| `cm monitor` | `cm mon` | CPU/RAM/Disk live view |
| `cm dashboard` | `cm dash` | Live dashboard |
| `cm uptime` | `cm up` | System uptime |
| `cm disk` | `cm df` | Disk usage per mount |
| `cm network` | `cm net` | Network interfaces |
| `cm top` | `cm top` | Top processes |
| `cm who` | `cm who` | Logged-in users |

### Nodes
| Command | Alias | Description |
|---------|-------|-------------|
| `cm node add -n NAME -H HOST -p 9999 -k KEY` | - | Add node |
| `cm node remove -n NAME` | `cm rmnode` | Remove node |
| `cm node install -H HOST -u USER -k KEY` | `cm nodeinstall` | Install node agent |
| `cm node monitor -n NAME` | `cm monnode` | Monitor node |
| `cm node gpu -n NAME` | `cm gpunode` | GPU telemetry |
| `cm node exec -n NAME "cmd"` | `cm exec` | Execute on node |
| `cm node job start -n NAME "cmd"` | `cm js` | Start async job |
| `cm node dashboard` | `cm dash` | Node overview |

### Docker
| Command | Alias | Description |
|---------|-------|-------------|
| `cm docker containers -s SERVER` | `cm dcls` | List containers |
| `cm docker stats -s SERVER` | `cm dcstats` | Container stats |
| `cm docker exec CONTAINER "cmd"` | `cm dcexec` | Exec in container |
| `cm docker logs CONTAINER -s SERVER` | `cm dclogs` | Container logs |
| `cm docker images -s SERVER` | - | List images |
| `cm docker cleanup -s SERVER` | - | Cleanup Docker |
| `cm docker compose PATH -s SERVER` | - | Run docker-compose |

### Firewall
| Command | Alias | Description |
|---------|-------|-------------|
| `cm firewall status` | `cm fw` | Firewall status |
| `cm firewall add-rule --port PORT` | `cm fwadd` | Add firewall rule |
| `cm firewall list-rules` | - | List rules |
| `cm firewall check-port --port PORT` | - | Check if port open |

### SSL Monitoring
| Command | Alias | Description |
|---------|-------|-------------|
| `cm ssl check DOMAIN` | `cm sslchk DOMAIN` | Check SSL certificate |
| `cm ssl check-all` | `cm sslall` | Check all domains |
| `cm ssl add DOMAIN` | - | Add domain |
| `cm ssl history` | - | Expiry history |

### Logs
| Command | Alias | Description |
|---------|-------|-------------|
| `cm logs -n NAME` | `cm log -n NAME` | System logs |
| `cm logagg search -p PATTERN` | `cm logsearch -p PATTERN` | Search logs |
| `cm logagg filter -l LEVEL` | - | Filter by level |
| `cm logagg subscribe -s SOURCE` | - | Tail logs live |
| `cm logagg sources` | - | List sources |

### File Operations
| Command | Alias | Description |
|---------|-------|-------------|
| `cm transfer -s SERVER -l LOCAL -r REMOTE` | `cm cp` | Upload/download |
| `cm sync` | `cm sync` | Sync directories |
| `cm find -n NAME -p PATH` | `cm find` | Search files |

### Webhooks & Alerts
| Command | Alias | Description |
|---------|-------|-------------|
| `cm webhooks add --name NAME --url URL` | - | Add webhook |
| `cm webhooks send MSG` | `cm whsend MSG` | Send message |
| `cm webhooks test -n NAME` | - | Test webhook |
| `cm watcher check` | `cm wtchk` | Check watchers |

### ACL & Security
| Command | Alias | Description |
|---------|-------|-------------|
| `cm acl users` | `cm aclu` | List users |
| `cm acl add-user -u USER -p PASS -r ROLE` | `cm acladd` | Add user |
| `cm acl remove-user -u USER` | `cm aclrm` | Remove user |
| `cm acl roles` | - | List roles |

### Cost & Tunnels
| Command | Alias | Description |
|---------|-------|-------------|
| `cm cost estimate -p PROVIDER -i INSTANCE` | `cm costest` | Estimate cost |
| `cm cost compare -i INSTANCE` | - | Compare providers |
| `cm tunnel add --name NAME --host HOST` | `cm tunadd` | Add tunnel |
| `cm tunnel start -n NAME` | `cm tunstart` | Start tunnel |
| `cm tunnel stop -n NAME` | `cm tunstop` | Stop tunnel |
| `cm tunnel quick --host HOST -l PORT -r PORT` | - | Quick tunnel |

### Database
| Command | Alias | Description |
|---------|-------|-------------|
| `cm database status -s SERVER` | `cm dbstatus` | Database status |
| `cm database query -s SERVER "SQL"` | `cm dbq` | Run query |
| `cm database backup -s SERVER -d DB` | `cm dbbak` | Backup database |
| `cm database list -s SERVER` | - | List databases |

### Utilities
| Command | Alias | Description |
|---------|-------|-------------|
| `cm encrypt FILE` | `cm enc FILE` | Encrypt file |
| `cm decrypt FILE` | `cm dec FILE` | Decrypt file |
| `cm export` | `cm exp` | Export config |
| `cm import -f FILE` | `cm imp -f FILE` | Import config |
| `cm cleanup` | `cm cleanup` | Remove old files |
| `cm report` | `cm report` | Usage report |
| `cm version` | `cm version` | Version info |

### Advanced
| Command | Alias | Description |
|---------|-------|-------------|
| `cm discover SUBNET` | - | Auto-discover nodes |
| `cm bench -s SERVER` | - | Benchmark |
| `cm audit -n NAME` | - | Security audit |
| `cm api --port 8080` | - | REST API |
| `cm notify setup-telegram` | - | Telegram alerts |
| `cm schedule add -n NAME "CMD"` | - | Schedule task |
| `cm ssh -n NAME` | - | Quick SSH |

---

## Examples

### Add a Server
```bash
cm add -n prod-server -H 192.168.1.100 -u root -k ~/.ssh/id_rsa
cm test -n prod-server
```

### Monitor Everything
```bash
cm monitor           # All servers
cm monitor -n prod   # Specific server
cm node gpu          # GPU usage on all nodes
cm reshistory snapshot  # Take resource snapshot
```

### Run Commands Everywhere
```bash
cm run "apt update && apt upgrade -y"        # Update all servers
cm run "df -h" --best                         # Run on best server
cm run "docker ps" -s "web,api"              # Specific servers
```

### Docker Management
```bash
cm docker containers --server web-1          # List containers
cm docker compose /path/to/docker-compose.yml --server web-1 -a up
cm docker stats --server web-1              # Container stats
cm docker exec web-1-container "ls -la"    # Run command in container
```

### Firewall Management
```bash
cm firewall add-rule --port 443 --proto tcp --action allow
cm firewall check-port --port 22
cm firewall backup --output fw_rules.json
```

### SSL Monitoring
```bash
cm ssl add example.com
cm ssl check-all                           # Check all domains
cm ssl history                             # Expiry history
```

### Webhooks
```bash
cm webhooks add --name alerts --url https://discord.com/api/webhooks/XXX --type discord
cm webhooks send --name alerts "Server is down!" --event error
```

### Process Watcher
```bash
cm watcher add --name nginx --process nginx --server web-1 --alert-on stop
cm watcher check                           # Check all watchers
cm watcher alerts                          # View recent alerts
```

### Cost Estimation
```bash
cm cost instances -p aws                   # List AWS instances
cm cost estimate -p aws -i t3.medium --hours 730
cm cost compare -i t3.medium              # Compare across providers
cm cost cheapest --ram 8                   # Find cheapest 8GB option
```

### SSH Tunnels
```bash
cm tunnel quick --host 10.0.0.5 -l 5432 -r 5432    # Quick tunnel
cm tunnel add --name db-tunnel --host 10.0.0.5 -l 3306 -r 3306
cm tunnel start --name db-tunnel
```

### Database Management
```bash
cm database list --server db-1 --type mysql -P root_password
cm database query --server db-1 "SHOW PROCESSLIST"
cm database backup --server db-1 --database myapp
```

### Custom Plugins
```bash
cm plugins add -n health-check -c "curl -s http://localhost/health"
cm plugins run -n health-check -s web-1
```

### Multi-User ACL
```bash
cm acl add-user -u admin -p secret123 -r admin
cm acl add-user -u viewer -p pass456 -r viewer
cm acl roles
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

## Security

CloudMesh takes security seriously:

- **API Authentication**: All REST API endpoints require `X-Api-Key` header
- **Node Auth Keys**: Per-node authentication with HMAC comparison
- **File Encryption**: Fernet encryption for config and sensitive data
- **SSH Policy**: RejectPolicy for unknown hosts (no silent acceptance)
- **Path Traversal Protection**: Sandboxed file operations on nodes
- **TLS Support**: Optional TLS encryption for node connections
- **ACL System**: Role-based access control (admin/viewer/custom roles)
- **Key Rotation**: Rotate `.secret.key` and node auth keys anytime

### REST API Security
```bash
cm api --port 8080
# Prints API key on startup - use it in all requests

curl -H "X-Api-Key: YOUR_KEY" http://127.0.0.1:8080/api/status
curl -H "X-Api-Key: YOUR_KEY" http://127.0.0.1:8080/api/servers
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

### Node Options
```bash
# Bind to specific interface
cm node start --bind 127.0.0.1

# Enable TLS
cm node start --tls-cert cert.pem --tls-key key.pem
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
  main.py              # CLI entry point (130+ commands)
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
    docker.py          # Docker management
    firewall.py        # Firewall management
    sslcheck.py        # SSL certificate monitor
    logagg.py          # Log aggregation
    reshistory.py      # Resource history
    plugins.py         # Custom plugins
    acl.py             # Multi-user ACL
    webhooks.py        # Webhook integrations
    watcher.py         # Process watcher
    cost.py            # Cost estimator
    tunnels.py         # SSH tunnel manager
    database.py        # Database manager
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

<details>
<summary><b>API returns 401 Unauthorized</b></summary>

```bash
# The API key is printed when starting the API
cm api --port 8080

# Use the key in your requests
curl -H "X-Api-Key: YOUR_KEY" http://127.0.0.1:8080/api/status
```
</details>

<details>
<summary><b>SSH connection rejected</b></summary>

CloudMesh uses RejectPolicy for security. Add the host to known_hosts first:
```bash
ssh-keyscan -H SERVER_IP >> ~/.ssh/known_hosts
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
