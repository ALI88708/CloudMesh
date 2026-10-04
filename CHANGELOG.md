# Changelog

All notable changes to CloudMesh are documented in this file.

The format follows the [SemVer](https://semver.org/) versioning scheme implemented by **MRSX PRO**.

## [Unreleased]

### Added
- **Smart diagnostics**: `cm diagnose` inspects resources, SSL expiries,
  watcher alerts, backup freshness, and drift, then prints severity-ranked
  findings with fix suggestions (`--json` for scripting, exit 2 on critical).
- **Drift detection**: `cm drift snapshot` records a baseline of managed
  state (servers, nodes, groups, schedules, templates, aliases, alert rules,
  never secrets); `cm drift check` reports added/removed/modified entries
  (exit 1 on drift); `cm drift list/clear` manage the baseline.

## [3.3.0] - 2026-10-04

### Stable SQLite backend release

SQLite is now the source of truth for all operational data types, each with
an encrypted/private store, a compatible JSON mirror, a one-time legacy
import (persistent marker — an empty table is valid data), and tests.

- **Wired managers**: servers, groups, nodes keyring, alerts, schedules,
  templates, aliases. `init_components` shares one `StorageManager`; `cm node`,
  `cm schedule`, `cm template`, `cm alias`, alerts, and `cm storage backup`
  all observe the same post-migration state in both directions.
- **Schema evolution**: `nodes` gains `tls`/`ca_file`; `schedules` gains
  `server`/`created`/`run_count`; `templates` gains `description`/`created`
  (added via `ALTER TABLE` on pre-existing databases).
- **Verify & health**: `cm migrate --verify` compares JSON vs SQLite
  (name sets for servers/nodes/groups, counts otherwise, exit 1 on drift);
  `cm doctor` adds storage checks (DB/key permissions, import markers,
  mirror consistency, backup count).
- **Release**: version single-sourced from package metadata (`get_version`
  falls back to 3.3.0); README documents migrate/storage commands.
- **Tests**: 185 passed, 1 skipped; coverage gate (25%) holds at ~37%.

### Upgrade notes
1. Upgrade, then run `cm migrate` (or `python -m cloudmesh.core.migrate`).
2. Confirm with `cm migrate --verify` and `cm doctor`.
3. Old JSON files remain as mirrors/backups; ACL data (`data/acl.json`)
   is still JSON-backed (scheduled follow-up).

## [3.2.3] - 2026-10-04

### Fixed (re-review dca74bc)
- **Restore resurrection**: legacy one-time import is now guarded by a persistent settings marker instead of table emptiness; with the marker present SQLite is authoritative and the JSON mirror is repaired from it (empty stays empty after restoring an empty backup). Same fix applied to groups.
- **Marker type trap**: `get_setting` JSON-decodes `"1"` to int `1`; marker checks normalize with `str(...)` so the guard actually matches (previously always false).
- **Duplicate `rename_group`**: removed the leftover JSON-only definition that shadowed the storage-wired one; rename now updates SQLite, the fresh-manager view, and the mirror.
- **Minor**: `cm storage` validates the action before creating `StorageManager` (no stray DB/key files on usage errors).
- **Tests**: resurrection scenario, once-only import, duplicate-definition guard, rename reflection (177 passed).

## [3.2.2] - 2026-10-04

### Fixed (follow-up review 2026-10-04)
- **Restore can no longer wipe the live DB**: safety-backup retention skips the restore source (`exclude`), the source is opened strictly read-only (`mode=ro`, never recreated if deleted), its CloudMesh schema is validated before and after the safety backup, and schema-less sources are refused without touching the live database.
- **Operational wiring to SQLite**: `ServerManager` and `GroupsManager` now use `StorageManager` as the source of truth (encrypted secrets), keep the legacy JSON config as a compatible mirror, and import legacy JSON entries once on init. `init_components` wires a shared `StorageManager`, so `cm add` and later `cm storage backup` cover the same data in both directions.
- **Old config backups encrypted**: `SecurityManager` backups now store raw encrypted config bytes with 0600 permissions (was decrypted plaintext with 0666); `restore_backup` accepts both new encrypted and legacy plaintext formats.
- **Tests**: new `test_server_storage.py` (manager↔storage visibility, legacy import, duplicates), restore `max_backups=1` source-protection and empty-DB refusal tests, config-backup encryption tests; updated the concurrent-backup test to the encrypted format. Suite: 174 passed.

## [3.2.1] - 2026-10-04

### Fixed (v3.2.0 review hardening)
- **Secrets encryption**: server passwords and node auth keys are always Fernet-encrypted in SQLite; keys auto-created with 0600 perms; legacy plaintext rows handled without data loss; misleading duplicate logs fixed.
- **Private file perms**: `cloudmesh.db`, `.secret.key`, and backups created 0600 (dirs 0700) on POSIX, matching queue storage.
- **Backup/restore**: backups use the SQLite backup API with unique names and validated `max_backups`; restore validates SQLite header, blocks path traversal, uses the backup API with safety backup and WAL checkpoint.
- **Migration**: `python -m cloudmesh.core.migrate --dry-run` writes nothing; template dicts and alias dicts handled; storage `False` returns recorded as errors; decrypt failures recorded; `success` is False whenever errors exist; `--base-dir` supported with proper exit codes.
- **CLI wiring**: new `cm migrate` and `cm storage <backup|list|restore>` commands connect the SQLite backend to operational commands; all `from core.` lazy imports fixed to `from cloudmesh.core.`; `plugins` missing `load_servers` fixed; reshistory auto-loop uses package import.
- **Tests**: new `cloudmesh/tests/test_storage.py` (encryption, perms, backup/restore, dry-run, templates, error success flag) now runs in the official suite.

## [3.2.0] - 2026-10-03

### ⚠️ BREAKING CHANGES
- **Full SQLite Backend**: Extended SQLite storage to cover all data types (servers, nodes, groups, alerts, ACL, aliases, templates, schedules)
  - Previously only task queue used SQLite (v3.1.0)
  - All JSON-based data now migrated to SQLite
  - Automatic migration script included (`core/migrate.py`)
  - Old JSON files backed up to `backups/json_backup_<timestamp>/` before migration
  - **Migration required**: Run `python -m cloudmesh.core.migrate` after upgrading to v3.2.0

### Added
- **Extended StorageManager**: New tables in `core/storage.py` for all data types
  - Servers, nodes, groups, settings, alerts, ACL users/roles, aliases, templates, schedules
  - Extends existing queue storage with additional tables
  - Built-in backup and restore functionality
  - Thread-safe operations with WAL mode
- **MigrationManager**: New `core/migrate.py` for seamless JSON → SQLite migration
  - Migrates all existing data including encrypted config
  - Preserves passwords, auth keys, and all settings
  - Dry-run mode for testing (`--dry-run`)
  - Detailed error reporting
- **Test Suite**: New `core/test_storage.py` for testing storage operations

### Changed
- **Database Schema**: Extended existing `cloudmesh.db` with additional tables
  - Existing queue tables remain unchanged
  - New tables: servers, nodes, groups, group_members, settings, alert_rules, alert_history, alert_cooldowns, acl_users, acl_roles, aliases, templates, schedules

### Migration Guide
1. Upgrade to v3.2.0 via pip or installer
2. Run migration: `python -m cloudmesh.core.migrate`
3. Verify migration: Check new tables exist in `cloudmesh.db`
4. Old JSON files are backed up automatically
5. If issues occur, restore from backup and report bug

### Technical Details
- Database: SQLite with WAL mode (existing from v3.1.0)
- Schema: Extended with normalized tables and foreign key constraints
- Encryption: Existing `.secret.key` reused for sensitive data
- Backups: Database backups stored in `backups/` directory
- Compatibility: Python 3.10+ (no change)

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