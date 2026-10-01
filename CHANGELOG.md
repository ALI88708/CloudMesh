# Changelog

All notable changes to CloudMesh are documented in this file.

The format follows the [SemVer](https://semver.org/) versioning scheme implemented by **MRSX PRO**.

## [3.1.0] - 2026-10-01

### Changed
- Queue jobs are now stored in a SQLite database with transactional writes and a 30-second busy timeout.
- Existing JSON queue records are migrated automatically on first startup; legacy files remain available as a migration backup.
- The database is created with restrictive POSIX permissions, and malformed legacy records stop migration with an explicit error.

## [3.0.2] - 2026-10-01

### Added
- Queue jobs can declare CPU, RAM, and disk resource claims independently of node eligibility minimums; omitted claims retain the previous threshold behavior.

### Fixed
- Configuration and encryption-key persistence now use atomic writes; concurrent backup creation reserves unique filenames.
- SSH command execution drains stdout and stderr concurrently and reports useful stderr, exit status, and timeout diagnostics.
- Node TLS startup now rejects incomplete certificate/key pairs instead of silently running without TLS.
- Server OS checks report the live probe result, and remote database failures no longer appear as successful empty results.

## [3.0.1] - 2026-10-01

### Fixed
- Queue workers now recover stale `dispatching` records after controller restarts instead of leaving those jobs stuck indefinitely.
- Node agents now report previously running jobs as `unknown` after restart when their final outcome cannot be confirmed.
- Queue and node job state files are replaced atomically to reduce the risk of corrupted records after an interrupted write.
- Invalid persisted node-job records are logged rather than silently discarded.

## [3.0.0] - 2026-10-01

### Added
- Adaptive scheduling now weighs CPU, RAM, and free disk space; jobs can require minimum disk capacity.
- Added safe failover: ambiguous running jobs are never replayed by default; `--idempotent` permits one retry after a sustained node outage.
- Queue workers use an exclusive coordinator lock; `CLOUDMESH_QUEUE_DIR` can point controllers at shared queue storage.
- Node agents cache telemetry briefly and expose a persistent node ID to reduce repeated probes and identify nodes.
- Node connections can use verified TLS with `cm node add --tls` and an optional private `--ca-file`.
- Node-key configuration is written atomically with restrictive Unix permissions.

## [2.3.2] - 2026-10-01

### Added
- `cm test --suite` runs the complete project test suite; `--coverage` adds a per-file coverage report.
- CI now executes the suite through the CLI and publishes coverage results in the job log.
- Added tests for the test-runner command while preserving `cm test --name` connection checks.

## [2.3.1] - 2026-10-01

### Fixed
- Shell completions now suggest nested commands and context-appropriate options in Bash, Zsh, and PowerShell.
- Fixed Zsh subcommand completion using the wrong command-line word position.
- Generated shell scripts use Unix line endings so Bash can source them on Windows.

## [2.3.0] - 2026-10-01

### Added
- **Priority and resource-aware task queue** — queue jobs with priority 0–9 and minimum free CPU/RAM requirements.
- **Queue worker** — `cm queue worker` dispatches higher-priority jobs first and keeps waiting jobs until a suitable node is available.

## [2.2.0] - 2026-09-30

### Added
- **Smart task queue** — `cm queue submit` selects the configured node with the best available CPU and memory resources, tracks remote job status, and supports listing and cancellation.
- **Safe dispatch failover** — retries another node only when the client can confirm the request was not sent; ambiguous requests are not replayed.

## [2.1.1] - 2026-09-30

### Fixed
- Directory sync now stops and reports source listing/download errors instead of treating an empty temporary directory as success.
- Cancelling an asynchronous node job terminates its process, and the worker preserves the cancelled status.
- Safe upload append modes preserve existing file contents; write modes continue to truncate.
- Node clients now read fragmented response-length headers completely and report premature connection closes.

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