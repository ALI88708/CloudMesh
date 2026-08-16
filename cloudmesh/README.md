# CloudMesh

Connect multiple devices and servers into one unified resource pool. Monitor, manage, and distribute workloads from a central controller.

## Quick Start

### Windows
```powershell
cm_for-windows.bat
```

### Linux / macOS
```bash
chmod +x cm_for-linux.sh
./cm_for-linux.sh
```

### Shortcut (Windows)
After first install, use `cm` from anywhere:
```powershell
cm --help
cm monitor --local
cm interactive
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Server Management** | Add servers via SSH, monitor resources |
| **Cloud Nodes** | Lightweight TCP agents on any device |
| **GPU Telemetry** | Monitor GPU usage, VRAM, temperature |
| **Async Jobs** | Run background tasks, check status later |
| **Task Slicer** | Distribute files across servers by resources |
| **Auto-Sync** | Sync local files to servers automatically |
| **Live Dashboard** | Real-time monitoring with Rich TUI |
| **File Transfer** | Upload/download between controller and servers |
| **Directory Sync** | Keep directories in sync across servers |
| **Package Deploy** | Install packages on all servers at once |
| **Alerts** | Set threshold alerts for CPU/RAM/Disk |
| **Device Groups** | Group servers and run commands on groups |
| **Failover** | Auto-retry on different server if one fails |
| **Backups** | Manage backups with rotation and verification |
| **Command History** | Log and search all executed commands |
| **Ping** | Quick ping all servers and nodes |
| **Uptime** | Show uptime of all connected servers |
| **Top Processes** | View top processes by CPU/RAM usage |
| **Disk Detail** | Detailed disk usage per mount point |
| **Network Info** | Show network interfaces on servers |
| **Who** | Show who's logged in on servers |
| **Find Files** | Search for files on remote servers |
| **Server Logs** | View recent system logs from servers |
| **Config Export/Import** | Export and import configuration |
| **File Encryption** | Encrypt/decrypt files with Fernet |
| **Speed Test** | Network latency test between servers |
| **Subnet Scan** | Scan subnet for CloudMesh nodes |
| **Cleanup** | Remove old logs, backups, and temp files |
| **Usage Report** | Generate JSON report of all resources |
| **Command Aliases** | Create shortcuts for frequent commands |
| **Version Info** | Show version and platform details |
| **Auto-Discovery** | Scan network for CloudMesh nodes |
| **Benchmark** | CPU/RAM/Disk performance testing |
| **Schedule** | Schedule recurring commands |
| **Notifications** | Telegram/Discord alert integration |
| **REST API** | HTTP API for integrations |
| **Config Profiles** | Save/load multiple configurations |
| **Security Audit** | Check server security settings |
| **Quick SSH** | Generate SSH commands instantly |
| **Templates** | Reusable command templates with variables |
| **Network Map** | Visual overview of all devices |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  CloudMesh                          │
│                                                     │
│  ┌──────────────┐         ┌──────────────┐         │
│  │  Controller  │ ←─SSH─→ │    Server    │         │
│  │  (your PC)   │         │  (cloud VM)  │         │
│  └──────┬───────┘         └──────────────┘         │
│         │                                           │
│         │ ←─TCP:9999─→ ┌──────────────┐            │
│         │               │  Node Agent  │            │
│         │               │  (any device)│            │
│         │               └──────────────┘            │
│         │                                           │
│         │ ←─TCP:9999─→ ┌──────────────┐            │
│         └──────────────→│  Node Agent  │            │
│                         │  (GPU server)│            │
│                         └──────────────┘            │
└─────────────────────────────────────────────────────┘
```

**Two connection methods:**
- **SSH** - For servers with SSH access (Linux, Windows with OpenSSH)
- **TCP Node** - Lightweight agent on any device (port 9999)

---

## Commands Reference

### General
```bash
cm --help                  # Show all commands
cm interactive             # Interactive TUI menu
cm monitor --local         # Monitor this machine
cm dashboard --live        # Live dashboard
```

### Server Management (SSH)
```bash
cm server add -n NAME -H HOST -u USER [-p PORT] [-k KEY]
cm server remove -n NAME
cm server list
cm server test -n NAME
cm server info -n NAME
```

**Example:**
```bash
cm server add -n myserver -H 192.168.1.100 -u root -k ~/.ssh/id_rsa
cm server test -n myserver
cm monitor -n myserver
```

### Cloud Nodes (TCP Agent)
```bash
cm node add -n NAME -H HOST [-p PORT] -k AUTH_KEY
cm node remove -n NAME
cm node list
cm node test -n NAME
cm node info -n NAME
cm node monitor [-n NAME]
cm node gpu [-n NAME]
cm node exec -n NAME "COMMAND"
cm node install -H HOST -u USER [-k KEY]
cm node dashboard
```

**Example:**
```bash
# Install node on remote server
cm node install -H 192.168.1.100 -u root -k ~/.ssh/id_rsa

# Add the node
cm node add -n gpu-server -H 192.168.1.100 -p 9999 -k abc123xyz

# Monitor
cm node monitor -n gpu-server
cm node gpu -n gpu-server
```

### Async Jobs
```bash
cm node job start -n NAME "COMMAND" [-t TIMEOUT]
cm node job status -n NAME -j JOB_ID
cm node job list -n NAME
cm node job kill -n NAME -j JOB_ID
```

**Example:**
```bash
cm node job start -n gpu-server "python train_model.py" -t 3600
cm node job status -n gpu-server -j a1b2c3d4e5f6
cm node job list -n gpu-server
```

### Task Slicing
```bash
cm slice -f "file1,file2,file3" [-s "server1,server2"]
cm slice -f "*.py" -e "python {file}"
```

**Example:**
```bash
cm slice -f "data1.csv,data2.csv,data3.csv" -s "s1,s2"
cm slice -f "model_*.py" -e "python {file}" -s "gpu1,gpu2"
```

### Auto-Sync
```bash
cm autosync -l LOCAL_DIR --to-server SERVER [--remote-to REMOTE_PATH]
```

**Example:**
```bash
cm autosync -l ./myproject --to-server gpu-server --remote-to /opt/project
```

### Run Commands
```bash
cm run "COMMAND"                    # Run on all servers
cm run "COMMAND" --best             # Run on best server
cm run "COMMAND" -s "s1,s2"        # Run on specific servers
```

### File Transfer
```bash
cm transfer -f LOCAL_FILE --to-server SERVER [-r REMOTE_PATH]
cm transfer --from-server SERVER -r REMOTE_FILE [-f LOCAL_PATH]
cm transfer --from-server S1 --to-server S2 -r REMOTE_PATH
```

### Directory Sync
```bash
cm sync -l LOCAL_DIR --to-server SERVER [--remote-to REMOTE_PATH]
cm sync --from-server SERVER --remote-from REMOTE_DIR [-l LOCAL_DIR]
```

### Deploy Packages
```bash
cm deploy -i PACKAGE_NAME          # Install on all servers
cm deploy -c PACKAGE_NAME          # Check if installed
cm deploy -s "SCRIPT" -n SERVER    # Run script on server
```

### Alerts
```bash
cm alerts -a "NAME,METRIC,THRESHOLD"   # Add rule
cm alerts --list-rules                   # List rules
cm alerts --check                        # Check now
cm alerts --history                      # View history
```

**Example:**
```bash
cm alerts -a "high-cpu,cpu,80"
cm alerts -a "low-disk,disk,90,myserver"
```

### Groups
```bash
cm group create -n NAME
cm group add -g GROUP -d DEVICE
cm group run -g GROUP "COMMAND"
cm group list
```

### History
```bash
cm history --record              # Record snapshot
cm history -n SERVER             # View history
cm history --stats SERVER        # View stats
```

### Backup
```bash
cm backup run -n SERVER
cm backup list -n SERVER
cm backup restore -n SERVER -j JOB_ID
cm backup verify -n SERVER -j JOB_ID
```

### Ping All
```bash
cm ping                    # Ping all servers and nodes
cm ping --no-nodes         # Ping servers only
```

### Uptime
```bash
cm uptime                  # All servers
cm uptime -n server1       # Specific server
```

### Top Processes
```bash
cm top                     # Top 5 by CPU on all servers
cm top -n server1          # Specific server
cm top --sort ram -l 10    # Top 10 by RAM
```

### Disk Detail
```bash
cm disk                    # All servers
cm disk -n server1         # Specific server
```

### Network
```bash
cm network                 # All servers
cm network -n server1      # Specific server
```

### Who (Logged In)
```bash
cm who                     # All servers
cm who -n server1          # Specific server
```

### Find Files
```bash
cm find -n server1 "*.log"
cm find -n server1 -p /var/log "*.conf"
```

### Server Logs
```bash
cm logs -n server1
cm logs -n server1 -f /var/log/auth.log -l 50
```

### Export/Import Config
```bash
cm export -f backup.json
cm import -f backup.json
```

### Encrypt/Decrypt
```bash
cm encrypt secret.txt
cm decrypt secret.txt.encrypted -k YOUR_KEY
```

### Speed Test
```bash
cm speed                   # All servers
cm speed -n server1 -t 8.8.8.8 -c 5
```

### Scan Subnet
```bash
cm scan 192.168.1.0/24
cm scan 10.0.0.0/24 --port 9999
```

### Cleanup
```bash
cm cleanup                 # Remove files older than 7 days
cm cleanup -d 30           # Remove files older than 30 days
```

### Report
```bash
cm report                  # Save to cloudmesh_report.json
cm report -f myreport.json
```

### Aliases
```bash
cm alias -n ls --cmd "ls -la"
cm alias -l                # List all aliases
cm alias -r ls             # Remove alias
```

### Version
```bash
cm version
```

### Auto-Discovery
```bash
cm discover 192.168.1.0          # Scan subnet
cm discover 10.0.0 --port 9999   # Custom port
```

### Benchmark
```bash
cm bench                         # Local benchmark
cm bench -s server1              # Remote server
```

### Schedule
```bash
cm schedule add -n monitor "cm ping" -i 300    # Every 5 min
cm schedule add -n cleanup "cm cleanup -d 7" -i 86400  # Daily
cm schedule list                               # View all
cm schedule toggle -n monitor                  # Enable/disable
cm schedule remove -n monitor                  # Delete
```

### Notifications
```bash
cm notify setup-telegram --token BOT_TOKEN --chat-id CHAT_ID
cm notify setup-discord --webhook WEBHOOK_URL
cm notify send "Server is down!"
cm notify status
```

### REST API
```bash
cm api                          # Start on port 8080
cm api --port 9090              # Custom port

# Endpoints:
# GET /api/status
# GET /api/servers
# GET /api/nodes
# GET /api/exec/{server}?cmd={command}
```

### Config Profiles
```bash
cm profile list                 # List profiles
cm profile save -n production   # Save current config
cm profile load -n production   # Load profile
cm profile delete -n production # Delete profile
```

### Security Audit
```bash
cm audit                        # Audit all servers
cm audit -n server1             # Audit specific server
```

### Quick SSH
```bash
cm ssh -n server1               # Generate SSH command
cm ssh -H 192.168.1.100 -u root
```

### Templates
```bash
cm template add -n deploy "rsync -avz {src} {user}@{host}:{dst}" -d "Deploy files"
cm template add -n update "ssh {user}@{host} 'apt update && apt upgrade -y'"
cm template list
cm template run -n deploy -p "src=./dist,host=server1,user=root,dst=/opt/app"
cm template remove -n deploy
```

### Network Map
```bash
cm map                          # Show all devices
```

---

## Installation Options

### Fresh Install
Run the installer for the first time - it sets up everything automatically.

### Update
If already installed, run the installer again and choose **3. Update**:
- Keeps your auth keys and server list
- Updates Python code and dependencies

### Factory Reset
Choose **2. Factory Reset** from the installer menu:
- Deletes all data (keys, config, backups)
- Reinstalls everything from scratch

### Uninstall
Choose **1. Uninstall** from the installer menu:
- Removes everything completely

---

## Node Installation

### Method 1: Local Install (same network)
```bash
# Run installer on the target device
chmod +x cm_for-linux.sh
./cm_for-linux.sh
```

### Method 2: Remote Install (via SSH)
```bash
cm node install -H SERVER_IP -u USER -k SSH_KEY
```

### Method 3: Manual Install
```bash
# Copy the installer to the target device
scp cm_for-linux.sh user@server:/tmp/
ssh user@server "chmod +x /tmp/cm_for-linux.sh && /tmp/cm_for-linux.sh"
```

---

## Configuration

### Config Files
| File | Location | Description |
|------|----------|-------------|
| `.node_keys.json` | `cloudmesh/` | Node connection keys |
| `cloudmesh.json` | `~/.cloudmesh/` | Server configurations |
| `.node_key` | `~/.cloudmesh-node/` | Node authentication key |

### Security
- Auth keys are auto-generated (32-char hex)
- SSH keys preferred over passwords
- Config encrypted with Fernet (AES-128-CBC)
- Auto-backups before config changes
- Path traversal protection on file operations

---

## Supported Platforms

| Platform | Controller | Node Agent |
|----------|------------|------------|
| Windows  | Yes | Yes |
| Linux    | Yes | Yes |
| macOS    | Yes | Yes (with WSL) |

### Package Managers (for auto-installing Python)
| Manager | Platform |
|---------|----------|
| winget | Windows 10/11 |
| chocolatey | Windows |
| scoop | Windows |
| apt | Ubuntu/Debian |
| yum/dnf | CentOS/RHEL/Fedora |
| pacman | Arch |
| zypper | openSUSE |
| apk | Alpine |

---

## Requirements

### Controller
- Python 3.8+
- SSH client (for server connections)

### Node Agent
- Python 3.8+ (auto-installed if missing)
- psutil (optional, for detailed metrics)

### Dependencies (auto-installed)
- rich - Terminal UI
- paramiko - SSH connections
- psutil - System monitoring
- cryptography - Encryption

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'rich'"
```powershell
# Reinstall dependencies
%USERPROFILE%\CloudMesh\venv\Scripts\pip.exe install -r cloudmesh\requirements.txt
```

### "Connection refused" when connecting to node
```bash
# Make sure node is running
~/.cloudmesh-node/status.sh

# If not running, start it
~/.cloudmesh-node/start.sh
```

### "Auth failed" error
```bash
# Check the auth key on the node
cat ~/.cloudmesh-node/.node_key

# Re-add the node with the correct key
cm node add -n NAME -H HOST -p 9999 -k CORRECT_KEY
```

### Node agent not starting
```bash
# Check logs
cat ~/.cloudmesh-node/cloudmesh_node.log

# Check if port is in use
netstat -tlnp | grep 9999
```

---

## License

MIT

---

## Make And Build By MRSX PRO