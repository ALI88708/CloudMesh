<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/ALI88708/CloudMesh/main/1.png">
  <img src="https://raw.githubusercontent.com/ALI88708/CloudMesh/main/1.png" alt="CloudMesh" width="200">
</picture>

# CloudMesh

### One Console to Control Them All

Connect multiple devices and servers into one unified resource pool.
Monitor, manage, and distribute workloads from a single terminal.

#### Made By MRSX PRO

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](License)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-blue?style=for-the-badge)](https://github.com/ALI88708/CloudMesh)
[![Commands](https://img.shields.io/badge/Commands-155+-orange?style=for-the-badge)](https://github.com/ALI88708/CloudMesh)
[![Version](https://img.shields.io/badge/Version-2.1.0-brightgreen?style=for-the-badge)](https://github.com/ALI88708/CloudMesh/releases)
[![Tests](https://img.shields.io/badge/Tests-63%20Passed-brightgreen?style=for-the-badge)](https://github.com/ALI88708/CloudMesh/actions)
[![Stars](https://img.shields.io/github/stars/ALI88708/CloudMesh?style=for-the-badge&color=yellow)](https://github.com/ALI88708/CloudMesh/stargazers)
[![Forks](https://img.shields.io/github/forks/ALI88708/CloudMesh?style=for-the-badge&color=blue)](https://github.com/ALI88708/CloudMesh/network/members)
[![Issues](https://img.shields.io/github/issues/ALI88708/CloudMesh?style=for-the-badge&color=orange)](https://github.com/ALI88708/CloudMesh/issues)
[![License](https://img.shields.io/github/license/ALI88708/CloudMesh?style=for-the-badge&color=green)](License)
[![Security](https://img.shields.io/badge/Security-Hardened-red?style=for-the-badge)](SECURITY.md)
[![Status](https://img.shields.io/badge/Auth-bcrypt%20%2B%20Lockout-purple?style=for-the-badge)](SECURITY.md)

<br>

[![Build](https://img.shields.io/badge/Build-Passing-brightgreen?style=flat-square&logo=githubactions&logoColor=white)](https://github.com/ALI88708/CloudMesh/actions)
[![Tests](https://img.shields.io/badge/tests-63_passed-brightgreen?style=flat-square)](https://github.com/ALI88708/CloudMesh/actions)
[![Coverage](https://img.shields.io/badge/coverage-on_Ci%2FCD-blue?style=flat-square)](https://github.com/ALI88708/CloudMesh/actions)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Lint](https://img.shields.io/badge/linting-ok-green?style=flat-square)](https://github.com/ALI88708/CloudMesh/actions)
[![Deps](https://img.shields.io/badge/dependencies-verified-green?style=flat-square)](cloudmesh/requirements.txt)

**Security Badges:**

[![Auth](https://img.shields.io/badge/Auth-bcrypt%20|%20lockout-purple?style=flat-square)](SECURITY.md)
[![Config](https://img.shields.io/badge/Config-Fernet_encrypted-blue?style=flat-square)](SECURITY.md)
[![Node SPA](https://img.shields.io/badge/Node-Ghost_Ports%20(SPA)-orange?style=flat-square)](SECURITY.md)
[![DDoS](https://img.shields.io/badge/DDoS-Rate_Limit%20%2B%20Ban-yellow?style=flat-square)](SECURITY.md)
[![Command](https://img.shields.io/badge/Command-Blocklist-red?style=flat-square)](SECURITY.md)
[![Panic](https://img.shields.io/badge/Panic-Shamir%202%2F3-red?style=flat-square)](SECURITY.md)

<br>

**155+ commands** | **Auto-discovery** | **Real-time monitoring** | **GPU telemetry** | **DDoS protection** | **Ghost Ports** | **Tripwire Keys** | **Shamir Panic** | **Remote Panic** | **Shell Completions**

</div>

---

## Why CloudMesh?

Managing multiple servers shouldn't mean juggling 10 SSH windows. CloudMesh gives you **one command** to control everything.

| Problem | CloudMesh Solution |
|---------|-------------------|
| SSH into each server manually | `cm run "command"` - run on all servers at once |
| No visibility into resource usage | `cm watch` - real-time monitoring dashboard |
| GPU servers hard to manage | `cm gpunode` - GPU telemetry from any node |
| No way to distribute work | `cm slice` - auto-slice tasks across servers by resources |
| Miss server alerts | `cm notify` - Telegram/Discord alerts |
| Docker scattered across servers | `cm docker` - manage containers on any node |
| Tamper-prone logs | `cm cmdlog --verify` - immutable hash chain detects tampering |
| Compromised keys | `cm panic` - rotate ALL keys (local + remote) in one command |
| Reactive scheduling | `cm weather` - predictive resource forecasting |
| Single-point trust | `cm trust` - distributed trust evaluation |
| Jobs lost on crash | `cm node job recover` - checkpoint & auto-recover jobs |
| TCP ports visible to scanners | `cm node start --spa` - Ghost Ports (SPA) hide your services |
| No SSH key management | `cm keys` - generate, list, deploy SSH keys |
| Batch command execution | `cm exec --all "cmd"` - run on all nodes at once |
| DDoS on your API | Built-in DDoS protection (rate limiting, banning, slowloris guard) |

---

## Quick Start

### pip install (Recommended)
Download [Python](https://www.python.org/) for Linux or Windows
```bash
pip install cloudmesh
cm --help
```

### Windows (Installer)
1. Download [Python](https://www.python.org/) and install it
2. Download [cm_for-windows.bat](cm_for-windows.bat) from this repo
3. Double-click to run it
4. Done! Use `cm --help` in PowerShell

### Linux (Installer)
Download [Python](https://www.python.org/) and install it first, then:
```bash
curl -sL https://raw.githubusercontent.com/ALI88708/CloudMesh/main/cm_for-linux.sh -o cm.sh
chmod +x cm.sh && ./cm.sh
```

### Update
```bash
cm update              # Self-update from GitHub (recommended)
pip install --upgrade cloudmesh  # Or via pip
```

### First Steps
```bash
cm --help              # Show all 155+ commands
cm status              # Quick overview of all servers/nodes
cm interactive         # Interactive TUI menu
cm mon --local         # Monitor this machine
cm watch               # Real-time monitoring dashboard
cm discover 192.168.1  # Scan your network for nodes
cm doctor              # Security & health check (15 checks)
cm exec --all "uptime" # Run command on all nodes
cm panic --dry-run     # Preview emergency key rotation
cm completions bash    # Enable shell completions
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
- **TCP Node** - Lightweight agent on any device (with optional Ghost Ports / SPA)

---

## Versioning Policy

CloudMesh follows [Semantic Versioning](https://semver.org/):

| Type | Format | When | Example |
|------|--------|------|---------|
| **Patch** | `2.0.x` | Security fixes, small bug fixes — no behavior changes | 2.0.1, 2.0.2 |
| **Minor** | `2.x.0` | New features added on top of stable base — backward compatible | 2.1.0, 2.2.0 |
| **Major** | `x.0.0` | Breaking changes that break compatibility with previous versions | 3.0.0 |

**Rule of thumb:** Patches ship when ready. Minors ship with new features. Majors only when absolutely necessary.

---

## Changelog - All Versions

### v2.0.0 (Latest)

#### New Commands
| Command | Description |
|---------|-------------|
| `cm exec --all "cmd"` | Batch execute command on all nodes at once |
| `cm watch` | Real-time monitoring dashboard (live CPU/RAM/Disk/GPU per node) |
| `cm keys generate` | Generate SSH key pair |
| `cm keys list` | List all managed SSH keys |
| `cm keys show` | Show public key content |
| `cm keys deploy` | Deploy public key to all servers |
| `cm keys remove-managed` | Remove managed key entry |
| `cm config list` | List all config files |
| `cm config export -d DIR` | Export all config to directory |
| `cm config import -d DIR` | Import config from directory |
| `cm config show` | Show config file contents |
| `cm completions bash` | Generate bash completions |
| `cm completions zsh` | Generate zsh completions |
| `cm completions powershell` | Generate PowerShell completions |
| `cm status` | Quick overview: servers, nodes, services, alerts |
| `cm doctor` | 15-point security and health check |
| `cm update` | Self-update from GitHub |
| `cm panic retry-pending` | Retry rotations that failed (nodes were offline) |

#### Security Patches (v2.0.0)
- **SPA Ghost Ports**: iptables ACCEPT rule now uses `-s source_ip` -- only the knocker can connect. Fail-closed: SPA mode refuses to start if iptables DROP fails.
- **Remote Panic Rotation**: `cm panic` now calls `rotate_key` on remote nodes (not just local). If a node is offline, rotation is saved for later retry with `cm panic retry-pending`.
- **SSH Tunnel Unification**: `build_ssh_cmd()` now has `strict=True` (default: host key verification enabled). Disabling strict mode emits a MITM warning.
- **DDoS Protection**: REST API has built-in rate limiting (30 req/min), connection limits (5 per IP, 100 total), IP auto-banning (5 failures = 5min ban), packet validation, and slowloris guard.

#### CI/CD
- GitHub Actions CI: runs on Python 3.10-3.13
- 58 security tests all passing

---

### v1.5.0

| Command | Description |
|---------|-------------|
| `cm update` | Self-update CloudMesh from GitHub releases |
| `cm status` | Quick overview of servers, nodes, services, alerts |
| `cm doctor` | 15-point security and health check |

- Fixed dead `tw` and `triw` aliases for tripwire

---

### v1.4.0 - Security Hardening

- **Centralized SSH**: All SSH connections use `ssh_util.py` with RejectPolicy (no silent host key acceptance). MITM warnings for disabled host key checking.
- **Telegram Validation**: Validates `chat_id` format before saving.
- **Firewall Allowlist**: Validates port/protocol inputs.
- **DB Temp Files**: Passwords written to temp files, auto-deleted after use.
- **Panic Remote Nodes**: `panic.py` connects to nodes for remote key rotation.
- **TLS/SPA Warnings**: Clear warnings when TLS or SPA is disabled.
- **Plugins Safety**: Warning when plugins use `shell=True`.

---

### v1.3.0 - Ghost Ports and Tripwire

#### New Commands
| Command | Description |
|---------|-------------|
| `cm node start --spa` | Start node with SPA (Single Packet Authorization) |
| `cm node start --spa --spa-port 9998` | Custom UDP port for SPA |
| `cm node start --spa --spa-window 10` | TCP stays open N seconds after knock |
| `cm tripwire plant --node NAME --host HOST` | Plant a tripwire trap key |
| `cm tripwire list` | List all planted tripwires |
| `cm tripwire check` | Check if any tripwire was triggered |
| `cm tripwire remove --node NAME` | Remove a tripwire |
| `cm panic setup` | Split panic key into 3 Shamir shares |
| `cm panic execute --share 1 --share 2` | Execute panic with 2-of-3 shares |
| `cm panic shares` | View current share status |

**Ghost Ports (SPA):** Node listens on UDP silently. Controller sends a signed HMAC packet (knock). Node opens TCP for N seconds. Port scanners see nothing. iptables rules are added/removed automatically. Only the knocker IP can connect (source IP binding).

**Tripwire Keys:** Plant fake keys on honeypot servers. If anyone uses a tripwire key, you get an immediate alert. Zero false positives.

**Shamir Panic:** Panic key is split into 3 shares using Shamir's Secret Sharing over GF(p). Any 2 shares can execute panic. A single compromised device cannot trigger it alone.

---

### v1.2.0 - Security and Intelligence

#### New Commands
| Command | Description |
|---------|-------------|
| `cm cmdlog --verify` | Verify command log chain integrity (SHA-256 hash chain) |
| `cm panic` | Emergency: rotate ALL encryption keys and node auth keys |
| `cm panic --dry-run` | Preview what panic would do |
| `cm weather` | Resource weather forecast for all servers |
| `cm weather --learn` | Record current resource snapshot |
| `cm weather -s SERVER` | Hourly CPU/RAM forecast for specific server |
| `cm weather --clear` | Clear all weather data |
| `cm trust` | Distributed trust status for all nodes |
| `cm trust --scan` | Scan nodes and evaluate trust |
| `cm node job checkpoint -n NAME -j JOB_ID` | Save checkpoint of a running job |
| `cm node job recover` | List jobs that can be recovered |
| `cm node job recover --relaunch` | Auto-relaunch recoverable jobs |
| `cm node job checkpoints` | List all saved job checkpoints |

**Immutable Command Ledger:** Every command is logged with a SHA-256 hash chain. Any tampering breaks the chain and is detected instantly.

**Resource Weather:** Records CPU/RAM/Disk snapshots over time. Predicts when resources will be exhausted.

**Distributed Trust:** Controller pings all nodes and compares self-reported metrics vs actual measurements. Catches compromised or malfunctioning nodes.

**Job Checkpointing:** Running jobs can be checkpointed. If a node crashes, jobs are recovered from the last checkpoint.

---

## Complete Command Reference

### Server Management
| Command | Alias | Description |
|---------|-------|-------------|
| `cm server add -n NAME -H HOST -u USER -k KEY` | `cm add` | Add server via SSH |
| `cm server remove -n NAME` | `cm rm` | Remove server |
| `cm server list` | `cm ls` | List all servers |
| `cm server test -n NAME` | `cm test` | Test connection |
| `cm server info -n NAME` | `cm info` | Server details |
| `cm run "cmd"` | - | Run on all servers |
| `cm plan "cmd"` | - | Distribution plan |

### Monitoring
| Command | Alias | Description |
|---------|-------|-------------|
| `cm monitor` | `cm mon` | CPU/RAM/Disk live view |
| `cm dashboard` | `cm dash` | Live dashboard |
| `cm watch` | - | Real-time monitoring dashboard (v2.0.0) |
| `cm uptime` | `cm up` | System uptime |
| `cm disk` | `cm df` | Disk usage per mount |
| `cm network` | `cm net` | Network interfaces |
| `cm top` | - | Top processes |
| `cm who` | - | Logged-in users |
| `cm ping` | - | Ping all servers/nodes |
| `cm compare` | - | Compare devices |

### Node Management
| Command | Alias | Description |
|---------|-------|-------------|
| `cm node add -n NAME -H HOST -p 9999 -k KEY` | - | Add node |
| `cm node remove -n NAME` | `cm rmnode` | Remove node |
| `cm node list` | - | List all nodes |
| `cm node test -n NAME` | - | Test node connection |
| `cm node info -n NAME` | - | Node details |
| `cm node install -H HOST -u USER -k KEY` | `cm nodeinstall` | Install node agent |
| `cm node monitor -n NAME` | `cm monnode` | Monitor node |
| `cm node exec -n NAME "cmd"` | `cm exec` | Execute on node |
| `cm exec --all "cmd"` | - | Execute on all nodes (v2.0.0) |
| `cm node gpu -n NAME` | `cm gpunode` | GPU telemetry |
| `cm node dashboard` | - | Node dashboard |

### Node Jobs
| Command | Description |
|---------|-------------|
| `cm node job start -n NAME "cmd"` | Start async job |
| `cm node job status -n NAME -j ID` | Check job status |
| `cm node job list -n NAME` | List jobs |
| `cm node job kill -n NAME -j ID` | Kill a job |
| `cm node job checkpoint -n NAME -j ID` | Save job checkpoint |
| `cm node job checkpoints` | List all checkpoints |
| `cm node job recover` | List recoverable jobs |
| `cm node job recover --relaunch` | Auto-relaunch failed jobs |

### Docker
| Command | Alias | Description |
|---------|-------|-------------|
| `cm docker list-servers` | - | List servers with Docker |
| `cm docker containers -s SERVER` | `cm dcls` | List containers |
| `cm docker stats -s SERVER` | `cm dcstats` | Container stats |
| `cm docker exec CONTAINER "cmd"` | `cm dcexec` | Exec in container |
| `cm docker logs CONTAINER -s SERVER` | `cm dclogs` | Container logs |
| `cm docker images -s SERVER` | - | List images |
| `cm docker pull IMAGE -s SERVER` | - | Pull image |
| `cm docker compose PATH -s SERVER` | - | Run docker-compose |
| `cm docker cleanup -s SERVER` | - | Cleanup Docker |
| `cm docker prune -s SERVER` | - | Prune everything |

### Firewall
| Command | Alias | Description |
|---------|-------|-------------|
| `cm firewall status` | `cm fw` | Firewall status |
| `cm firewall add-rule --port PORT --proto PROTO --action ACT` | `cm fwadd` | Add firewall rule |
| `cm firewall remove-rule --port PORT` | - | Remove rule |
| `cm firewall list-rules` | - | List rules |
| `cm firewall check-port --port PORT` | - | Check if port open |
| `cm firewall backup` | - | Backup rules |
| `cm firewall load -f FILE` | - | Load rules from file |

### SSL Monitoring
| Command | Alias | Description |
|---------|-------|-------------|
| `cm ssl check DOMAIN` | `cm sslchk DOMAIN` | Check SSL certificate |
| `cm ssl check-all` | `cm sslall` | Check all domains |
| `cm ssl add DOMAIN` | - | Add domain |
| `cm ssl remove DOMAIN` | - | Remove domain |
| `cm ssl domains` | - | List domains |
| `cm ssl history` | - | Expiry history |
| `cm ssl renew-check` | - | Check renewal status |

### Logs
| Command | Alias | Description |
|---------|-------|-------------|
| `cm logs -n NAME` | `cm log -n NAME` | System logs |
| `cm logagg search -p PATTERN` | `cm logsearch -p PATTERN` | Search logs |
| `cm logagg filter -l LEVEL` | - | Filter by level |
| `cm logagg subscribe -s SOURCE` | - | Tail logs live |
| `cm logagg sources` | - | List sources |
| `cm logagg add-source --name NAME --path PATH` | - | Add log source |
| `cm logagg stats` | - | Log statistics |
| `cm logagg clear` | - | Clear log index |

### File Operations
| Command | Alias | Description |
|---------|-------|-------------|
| `cm transfer -s SERVER -l LOCAL -r REMOTE` | `cm cp` | Upload/download |
| `cm sync` | - | Sync directories |
| `cm find -n NAME -p PATH` | `cm find` | Search files |
| `cm autosync` | - | Auto-sync local dir to server |
| `cm backup` | - | Manage backups |

### SSH Keys (v2.0.0)
| Command | Description |
|---------|-------------|
| `cm keys generate` | Generate SSH key pair |
| `cm keys list` | List all managed SSH keys |
| `cm keys show` | Show public key content |
| `cm keys deploy` | Deploy public key to all servers |
| `cm keys remove-managed` | Remove managed key entry |

### Configuration (v2.0.0)
| Command | Description |
|---------|-------------|
| `cm config list` | List all config files |
| `cm config export -d DIR` | Export all config to directory |
| `cm config import -d DIR` | Import config from directory |
| `cm config show` | Show config file contents |
| `cm profile list` | List profiles |
| `cm profile save -n NAME` | Save current config as profile |
| `cm profile load -n NAME` | Load a profile |
| `cm profile delete -n NAME` | Delete a profile |

### Shell Completions (v2.0.0)
| Command | Description |
|---------|-------------|
| `cm completions bash` | Generate bash completions |
| `cm completions zsh` | Generate zsh completions |
| `cm completions powershell` | Generate PowerShell completions |

### Webhooks and Alerts
| Command | Alias | Description |
|---------|-------|-------------|
| `cm webhooks add --name NAME --url URL --type TYPE` | - | Add webhook |
| `cm webhooks send MSG` | `cm whsend MSG` | Send message |
| `cm webhooks test -n NAME` | - | Test webhook |
| `cm webhooks list` | - | List webhooks |
| `cm webhooks log` | - | Webhook log |
| `cm webhooks enable-all` | - | Enable all webhooks |
| `cm webhooks disable-all` | - | Disable all webhooks |
| `cm watcher check` | `cm wtchk` | Check watchers |
| `cm watcher add --name NAME --cmd CMD` | - | Add process watcher |
| `cm watcher remove --name NAME` | - | Remove watcher |
| `cm watcher alerts` | - | Watcher alerts |

### ACL and Security
| Command | Alias | Description |
|---------|-------|-------------|
| `cm acl users` | `cm aclu` | List users |
| `cm acl add-user -u USER -p PASS -r ROLE` | `cm acladd` | Add user |
| `cm acl remove-user -u USER` | `cm aclrm` | Remove user |
| `cm acl set-role -u USER -r ROLE` | - | Set role |
| `cm acl enable -u USER` | - | Enable user |
| `cm acl disable -u USER` | - | Disable user |
| `cm acl roles` | - | List roles |
| `cm acl add-role -r ROLE` | - | Add role |
| `cm acl remove-role -r ROLE` | - | Remove role |

### SSH Tunnels
| Command | Alias | Description |
|---------|-------|-------------|
| `cm tunnel add --name NAME --host HOST -l LPORT -r RPORT` | `cm tunadd` | Add tunnel |
| `cm tunnel start -n NAME` | `cm tunstart` | Start tunnel |
| `cm tunnel stop -n NAME` | `cm tunstop` | Stop tunnel |
| `cm tunnel quick --host HOST -l PORT -r PORT` | - | Quick tunnel |
| `cm tunnel list` | - | List tunnels |
| `cm tunnel status` | - | Tunnel status |
| `cm tunnel stop-all` | - | Stop all tunnels |

### Database
| Command | Alias | Description |
|---------|-------|-------------|
| `cm database status -s SERVER -t TYPE -P PASS` | `cm dbstatus` | Database status |
| `cm database query -s SERVER "SQL"` | `cm dbq` | Run query |
| `cm database backup -s SERVER -d DB` | `cm dbbak` | Backup database |
| `cm database list -s SERVER` | - | List databases |

### Schedule
| Command | Description |
|---------|-------------|
| `cm schedule add -n NAME "CMD" -i SECONDS` | Add schedule |
| `cm schedule remove -n NAME` | Remove schedule |
| `cm schedule list` | List schedules |
| `cm schedule toggle -n NAME` | Toggle schedule |

### Notifications
| Command | Description |
|---------|-------------|
| `cm notify setup-telegram --token TOKEN --chat-id CHAT_ID` | Setup Telegram |
| `cm notify setup-discord --webhook URL` | Setup Discord |
| `cm notify send "MESSAGE"` | Send notification |
| `cm notify status` | Notification status |

### Utilities
| Command | Alias | Description |
|---------|-------|-------------|
| `cm encrypt FILE` | `cm enc FILE` | Encrypt file |
| `cm decrypt FILE` | `cm dec FILE` | Decrypt file |
| `cm export` | `cm exp` | Export config |
| `cm import -f FILE` | `cm imp -f FILE` | Import config |
| `cm cleanup` | - | Remove old files |
| `cm report` | - | Usage report |
| `cm speed` | - | Network speed test |
| `cm scan SUBNET` | - | Scan subnet for nodes |
| `cm alias add -n NAME -c CMD` | - | Manage aliases |
| `cm version` | - | Version info |
| `cm map` | - | Network map |
| `cm template add -n NAME -c CMD` | - | Command templates |

### Advanced
| Command | Description |
|---------|-------------|
| `cm discover SUBNET` | Auto-discover nodes on network |
| `cm bench -s SERVER` | Benchmark server performance |
| `cm audit -n NAME` | Security audit (8 checks) |
| `cm api --port 8080` | Start REST API server |
| `cm ssh -n NAME` | Quick SSH command |
| `cm plugin add/run/list/remove` | Custom plugin management |

### Resource History
| Command | Description |
|---------|-------------|
| `cm reshistory snapshot` | Take resource snapshot |
| `cm reshistory show` | Show history |
| `cm reshistory summary` | Summary |
| `cm reshistory clear` | Clear history |

---

## Examples

### Add a Server
```bash
cm add -n prod-server -H 192.168.1.100 -u root -k ~/.ssh/id_rsa
cm test -n prod-server
```

### Monitor Everything
```bash
cm mon           # All servers
cm mon -n prod   # Specific server
cm watch         # Real-time dashboard
cm gpunode       # GPU usage on all nodes
```

### Run Commands Everywhere
```bash
cm run "apt update && apt upgrade -y"       # Update all servers
cm run "df -h" --best                        # Run on best server
cm run "docker ps" -s "web,api"             # Specific servers
cm exec --all "uptime"                       # Run on all nodes
```

### Quick Status
```bash
cm status       # Overview of servers, nodes, alerts
cm doctor       # 15-point health check
```

### Docker Management
```bash
cm dcls -s web-1                  # List containers
cm dcstats -s web-1               # Container stats
cm dcexec web-1-container "ls -la"  # Exec in container
cm docker cleanup -s web-1        # Cleanup unused containers
```

### Firewall Management
```bash
cm fwadd --port 443 --proto tcp --action allow
cm fw                              # Check status
cm firewall check-port --port 443  # Check if port open
```

### SSL Monitoring
```bash
cm ssl add example.com
cm sslall                          # Check all domains
cm ssl renew-check                 # Check renewal status
```

### Webhooks
```bash
cm webhooks add --name alerts --url https://discord.com/api/webhooks/XXX --type discord
cm whsend --name alerts "Server is down!" --event error
```

### SSH Tunnels
```bash
cm tunnel quick --host 10.0.0.5 -l 5432 -r 5432    # Quick tunnel
cm tunadd --name db-tunnel --host 10.0.0.5 -l 3306 -r 3306
cm tunstart --name db-tunnel
```

### Database Management
```bash
cm dbstatus -s db-1 -t mysql -P root_password
cm dbq -s db-1 "SHOW PROCESSLIST"
cm dbbak -s db-1 -d myapp
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

### Immutable Command Ledger
```bash
cm cmdlog --verify           # Check if command log was tampered with
# Chain intact - all 42 entries verified.
# Chain BROKEN at entry #17 - possible tampering detected.
```

### Emergency Panic Button
```bash
cm panic --dry-run           # Preview what would happen
cm panic                     # Rotate ALL keys (local + remote)
cm panic setup               # Split into 3 Shamir shares
cm panic execute --share 1 --share 2  # Execute with 2-of-3
cm panic rotate              # Rotate keys on all remote nodes
cm panic retry-pending       # Retry failed rotations (v2.0.0)
```

### Resource Weather Forecast
```bash
cm weather --learn           # Record current CPU/RAM (run periodically)
cm weather                   # See forecast for next hour
cm weather -s prod-server    # Hourly profile for one server
```

### Distributed Trust
```bash
cm trust --scan              # Ping all nodes and evaluate trust
cm trust                     # View trust status
```

### Job Checkpoint and Recovery
```bash
cm node job checkpoint -n gpu-1 -j abc123   # Save job progress
cm node job checkpoints                       # List all checkpoints
cm node job recover --relaunch                # Recover failed jobs
```

### Ghost Ports (SPA)
```bash
cm node start --spa                           # Start with SPA mode
cm node start --spa --spa-port 9998           # Custom UDP port
cm node start --spa --spa-window 10           # TCP stays open 10s
```
**How it works:** Node listens on UDP silently. Controller sends a signed HMAC packet. Node opens TCP for N seconds. Port scanners see nothing. Only the knocker's source IP can connect.

### Tripwire Keys
```bash
cm tripwire plant --node honeypot --host 10.0.0.99   # Plant trap
cm tripwire list                                     # View tripwires
cm tripwire check                                    # Check if triggered
cm tripwire remove --node honeypot                   # Remove trap
```

### SSH Key Management (v2.0.0)
```bash
cm keys generate            # Generate new key pair
cm keys list                # List all managed keys
cm keys show                # Show public key
cm keys deploy              # Deploy to all servers
```

### Shell Completions (v2.0.0)
```bash
cm completions bash         # Bash completions
cm completions zsh          # Zsh completions
cm completions powershell   # PowerShell completions
```

### Self Update (v2.0.0)
```bash
cm update                   # Update from GitHub
cm status                   # Quick overview
cm doctor                   # Run health checks
```

---

## Security

CloudMesh takes security seriously:

- **DDoS Protection**: Rate limiting (30 req/min), connection limits (5 per IP, 100 total), IP auto-banning (5 failures = 5min ban), packet validation, slowloris guard
- **API Authentication**: All REST API endpoints require `X-Api-Key` header
- **Node Auth Keys**: Per-node HMAC authentication
- **File Encryption**: Fernet encryption for config and sensitive data
- **SSH Policy**: RejectPolicy for unknown hosts (no silent acceptance)
- **Host Key Verification**: Default `StrictHostKeyChecking=yes` with MITM warnings when disabled
- **Path Traversal Protection**: Sandboxed file operations on nodes
- **TLS Support**: Optional TLS encryption for node connections
- **ACL System**: Role-based access control (admin/viewer/custom roles)
- **Key Rotation**: Rotate `.secret.key` and node auth keys anytime
- **Remote Panic Rotation**: Panic rotates keys on remote nodes too
- **Pending Retry**: Failed rotations saved and retriable offline
- **Immutable Command Ledger**: SHA-256 hash chain detects any log tampering
- **Emergency Panic Button**: One command rotates all keys and locks down access
- **Ghost Ports (SPA)**: TCP port invisible to scanners -- only signed UDP knock opens it
- **Source IP Binding**: SPA ACCEPT rules restricted to knocker IP only
- **Fail-Closed SPA**: Node refuses to start if iptables DROP fails
- **Tripwire Keys**: Fake keys that trigger automatic breach detection (zero false positives)
- **Shamir Panic 2-of-3**: Panic requires 2 of 3 key shares
- **Distributed Trust**: Controller-vs-self-report comparison catches compromised nodes
- **Job Checkpointing**: Save job progress periodically for crash recovery

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
| **pip install** | `pip install cloudmesh` -- simplest method |
| **Fresh Install** | Download installer, double-click, done |
| **Update** | `cm update` or `pip install --upgrade cloudmesh` |
| **Uninstall** | `pip uninstall cloudmesh` |

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
cm nodeinstall -H SERVER_IP -u root -k ~/.ssh/id_rsa
```

### Node Options
```bash
cm node start --bind 127.0.0.1       # Bind to specific interface
cm node start --tls-cert cert.pem --tls-key key.pem  # Enable TLS
cm node start --spa                  # Enable Ghost Ports (SPA)
cm node start --spa --spa-port 9998  # Custom UDP port
cm node start --spa --spa-window 10  # TCP open window in seconds
```

### What Gets Installed
```
~/.cloudmesh-node/
  cloudmesh_node.py       # Node agent
  .node_key               # Auth key
  .secret.key             # Encryption key
  start.sh                # Start script
  stop.sh                 # Stop script
  status.sh               # Status script
  cloudmesh-node.service  # Systemd service (auto-created)
```

---

## Project Structure

```
cloudmesh/
  main.py              # CLI entry point (155+ commands)
  requirements.txt     # Python dependencies
  core/
    server.py          # SSH server management
    monitor.py         # Resource monitoring
    scheduler.py       # Task scheduling
    node_client.py     # TCP node communication
    jobs.py            # Async job system
    gpu.py             # GPU telemetry
    features.py        # 20 utility features
    advanced.py        # 10 advanced features (API, DDoS, scheduler, etc.)
    security.py        # Encryption and audit
    ssh_util.py        # Centralized SSH with host key verification
    transfer.py        # File transfer
    sync.py            # Directory sync
    deploy.py          # Package deployment
    alerts.py          # Threshold alerts
    groups.py          # Device groups
    dashboard.py       # Live dashboard
    tui.py             # Interactive TUI
    history.py         # Command history
    cmdlog.py          # Immutable command ledger (SHA-256 hash chain)
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
    ddos.py            # DDoS protection (rate limiter, ban list, slowloris guard)
    panic.py           # Emergency key rotation + remote rotation + pending retry
    weather.py         # Resource weather forecast
    gossip.py          # Distributed trust evaluation
    checkpoint.py      # Job checkpoint manager
    shamir.py          # Shamir Secret Sharing over GF(p)
  node/
    cloudmesh_node.py  # Standalone node agent (SPA, DDoS, TLS)
  tests/
    test_security.py   # 58 security tests
  data/                # Auto-created config/state files
```

---

## Requirements

| Component | Requirement |
|-----------|------------|
| Controller | Python 3.8+, SSH client |
| Node Agent | Python 3.8+ (auto-installed) |
| OS | Windows 10+, Linux (Ubuntu/Debian/CentOS/Arch) |

### Dependencies (auto-installed)
- `rich` -- Beautiful terminal UI
- `paramiko` -- SSH connections
- `psutil` -- System monitoring
- `cryptography` -- File encryption

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
cm add -n NAME -H HOST -p 9999 -k YOUR_KEY
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

<details>
<summary><b>SPA mode: node refuses to start</b></summary>

SPA mode requires iptables. If the DROP rule fails, the node will refuse to start to avoid exposing the TCP port unprotected. Run as root or check iptables permissions.
</details>

<details>
<summary><b>Panic: some nodes were offline</b></summary>

```bash
# Retry pending rotations when nodes come back online
cm panic retry-pending
```
</details>

---

## License

MIT License - Free to use, modify, and distribute.

---

<div align="center">

**Created and Developed by MRSX PRO**

**GitHub:** [ALI88708](https://github.com/ALI88708)

**Repository:** [CloudMesh](https://github.com/ALI88708/CloudMesh)

All rights reserved. This project is maintained by **MRSX PRO**.

Star this repo if CloudMesh helps you! It motivates us to keep building.

[Star on GitHub](https://github.com/ALI88708/CloudMesh)

</div>
