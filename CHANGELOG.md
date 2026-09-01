# Changelog

All notable changes to CloudMesh are documented in this file.

The format follows the [SemVer](https://semver.org/) versioning scheme implemented by **MRSX PRO**.

## [2.1.0] - 2026-09-01

### Added
- **Alert severity levels** — `info`, `warning`, `critical`. Rules can set a base severity that auto-escalates when the threshold is exceeded by 20%+.
- **Alert cooldown** — per-rule notification cooldown (default 300s) to prevent spam. Cooldown state survives restarts.
- **Alert notifications** — alerts now push to configured **Telegram / Discord** channels automatically through the existing `NotifyManager`.
- **GPU panels** — `cm dashboard` and `cm watch` now show GPU model, utilization, memory and temperature for GPU-enabled nodes.
- **Auto resource history** — `cm reshistory auto start --interval 60` records snapshots in the background (stop/status supported).
- **Security: bcrypt password hashing** — ACL user passwords now use bcrypt (12 rounds) with a PBKDF2 fallback.
- **Security: brute-force lockout** — ACL accounts lock for 15 minutes after 5 failed attempts; auth events are audited to `data/acl_audit.log`.
- **Security: path traversal protection** — `restore_backup` now rejects paths outside the backups directory.
- **Security: command blocklist** — the node agent blocks destructive commands (`rm -rf /`, `mkfs`, `dd if=`, fork bombs, `shutdown`, etc.).
- **Security: upload mode validation** — the node agent only allows `w`, `a`, `wb`, `ab` file modes.
- **Security: exception auditing** — silent `except: pass` paths now log warnings via the `logging` module.

### Changed
- Repository username updated from `MrAli88708` to **`ALI88708`** across README, installers, docs and project metadata.
- README now displays the CloudMesh logo and fixed all badge links (Platform, Commands, Tests, Security point to real targets).
- `CONTRIBUTING.md` converted into a real contributing guide (setup, style, tests, PR workflow, SemVer).
- REST API `/api/status` and `/api/health` now report the real application version instead of a hardcoded value.
- Alerts rule format extended: `name,metric,threshold[,node][,severity][,cooldown][,operator]`.

### Fixed
- **`cm exec --all` routed to wrong handler** — removed the duplicate `exec` registration in the command table; the multi-node handler is now used.
- Silent failures in config/key permission handling now log properly.

## [2.0.0] - 2026-08-24

### Added
- Two-tier architecture: **Controller** and **Node** agents over raw TCP (port 9999) with auth keys.
- 155+ CLI commands covering server management, monitoring, deployment, scheduling, transfers, and more.
- Node features: GPU telemetry, async jobs, remote execute, file upload/download, key rotation.
- Security suite: DDoS protection, Ghost Ports (SPA), Tripwire keys, Shamir panic, remote panic rotation, encrypted config storage.
- `cm dashboard`, `cm watch`, interactive TUI, REST API.
- Windows and Linux one-line installers.
- CI/CD via GitHub Actions on Python 3.10 – 3.13.

---