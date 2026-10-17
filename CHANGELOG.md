# Changelog

All notable changes to CloudMesh are documented in this file.

The format follows the [SemVer](https://semver.org/) versioning scheme implemented by **MRSX PRO**.

## [3.5.0] - 2026-10-16 — Enterprise (stable)

This is the Enterprise stable release. The first release since 3.4.0, and the
one that makes failures visible: the command surface, the installers, and the
environment handling had all been shipping defects that no test could see.
Every item below shipped with a green suite; the suite now covers them. It is
also the release where the numbers this project advertises are derived rather
than remembered.

### Fixed — the command surface

- **`cm run "cmd"` no longer exits 0 in silence.** `add_subparsers(dest="command")`
  shared a destination with the positional argument holding the command to run,
  so the positional overwrote the command name, dispatch found no handler, and the
  process exited 0 with no output. The same breakage affected `cm group run`,
  `cm node exec`, `cm node job start`, `cm exec --all`, and `cm plugins add`.
- **`cm node job start` reaches its handler.** `node`'s sub-subparsers shared
  `dest="action"` with `node`'s own, so `start` was looked up in the node table,
  missed, and printed node help.
- **`cm node job checkpoint`, `recover`, and `checkpoints` answer again.** They
  exited 0 with no output after the job sub-subparsers moved to `job_action`,
  leaving `args.action` as `job`, which `cmd_node_job` did not handle — the same
  silent-exit class this release set out to remove. `cm node job` with no
  subcommand now reports usage and exits 2 instead of saying nothing.
- **A group with no subcommand prints help** (`cm server`, `cm node`, `cm queue`).
  The dispatch fallback took no arguments and raised `TypeError`.
- **An unknown command exits 1** with a message instead of exiting 0 silently.
- **Aliases are clones of their canonical parsers, not hand copies.** Each alias
  restated its canonical command's arguments by hand and had drifted: `cm mon
  --local`, advertised in the README, failed with "unrecognized arguments", and
  `cm cp` declared `--server`, `--local`, and `--direction`, none of which
  `cmd_transfer` reads, so it could not have worked at all. `_alias_of` now
  clones the canonical parser's actions, README and `CONTRIBUTING.md` examples
  were corrected to the forms the CLI accepts, and `test_alias_parity.py`,
  `test_documented_commands.py`, and `test_readme_commands.py` hold both.

### Fixed — crashes on first use

- `cm api` raised `NameError: time` — `time` was never imported.
- `cm panic rotate` raised `NameError: _load_config` — no such function existed.
- `cm panic retry-pending` raised `UnboundLocalError` — the manager was bound
  after the branch that used it.
- `cm weather` forecast paths raised `NameError: datetime`.
- Removed the `__import__("time")` / `__import__("datetime")` string hacks that
  hid all of the above.

### Fixed — security

- **Panic key rotation now persists to SQLite.** `PanicManager` read and wrote
  `.node_keys.json` directly while SQLite was the source of truth, so the next
  `NodeKeyring` construction rewrote the mirror from SQLite and silently restored
  the pre-panic keys. The emergency rotation did not stick.
- `.secret.key` is replaced atomically with owner-only permissions instead of a
  plain `write_bytes`, which created it world-readable on first use.
- **The SSH key registry `cm keys` writes at runtime is no longer committed.**
  `cloudmesh/.ssh_keys.json` was picked up by a test run and swept into the
  Git-detection commit. It is ignored alongside the rest of the runtime state
  the CLI writes next to the package.
- `cm panic --dry-run` and the rotation output now state that stored server
  passwords and node auth keys become undecryptable afterwards.
- `cm doctor` inspects the loaded modules and `build_ssh_cmd`'s signature instead
  of grepping source files for magic strings. The SSH check looked for
  `"MITMWarning"` while the class is `SSHWarning`, so it always reported FAIL.
- **Ten dependency advisories cleared.** `pip-audit` reported 10 known
  vulnerabilities across `cryptography==42.0.0` and `paramiko==3.4.0`, and the
  CI security job gates on it, so every run was going to fail. Both move to
  `cryptography==50.0.0` and `paramiko==5.0.0`; `pip-audit` now reports no known
  vulnerabilities.
- **Those two pins move as a pair, deliberately.** `cryptography` relocated
  `TripleDES` into `hazmat.decrepit` in 48.0.0, and that is the algorithm
  `paramiko`'s transport builds its cipher list from, so raising `cryptography`
  under `paramiko` 3.4 raises at import. `pyproject.toml` records the reason
  next to the dependency so a future bump does not split them.

### Fixed — storage and the environment

- **`SecurityManager` follows `CLOUDMESH_DIR`.** It resolved its base directory
  with an inline fallback, so a sandboxed `CLOUDMESH_DIR` moved the database
  while leaving `config.json` and the Fernet key behind in the package
  directory — a harness run then read state the developer's real install had
  written.
- **`cm doctor` reports the active data directory.** Every other row is the code
  inspecting itself, so a wrong `CLOUDMESH_DIR` produced an entirely green table
  while the user's data had moved somewhere they did not choose. A directory that
  does not exist renders `FAIL` rather than a healthy-looking path.
- **A nested `CLOUDMESH_DIR` no longer raises `FileNotFoundError`.**
  `backups_dir.mkdir(exist_ok=True)` had no `parents=True`, and
  `resolve_base_dir` returns its path without creating it.

### Fixed — the test suite

- **Subprocess tests no longer race the 10-second cap.** Five test files spawned
  real subprocesses under `pytest.ini`'s `timeout = 10` while carrying their own
  `timeout=60`. `test_windows_installer_extract.py` measured 8.7s cold against
  that cap and failed whenever the runner was loaded, and the suite badge guard
  in `test_release_metadata.py` collects the entire suite through a subprocess
  under the same cap while its own bound is 300 seconds. All of them carry their
  own `timeout` markers now. One `subprocess.run` in `test_completions.py` had no
  timeout at all.
- **A test file that no runner could collect is gone.**
  `cloudmesh/core/test_storage.py` sat outside `pytest.ini`'s `testpaths`, so it
  never ran in CI, and it crashed on a Windows console besides.
  `cloudmesh/tests/test_storage.py` covers the same operations in the official
  suite.

### Fixed — installers

- **The Linux installer runs at all.** `cm_for-linux.sh` and
  `cloudmesh/node/node-install.sh` were committed with CRLF endings, so bash
  failed with a syntax error on the first line. The one-line install documented in
  the README could never run. `.gitattributes` now pins the endings.
- **The Windows installer stops truncating `cloudmesh/core/__init__.py`.** It ran
  `echo. > core\__init__.py`, replacing the package re-exports with a blank line.
- **The Windows installer's extract step produces a project again.** `Copy-Item`
  into a destination that does not exist renames the source directory instead of
  nesting it, and the check that followed asserted the other shape — a fresh
  install put `main.py` flat at the project root with no `cloudmesh\`
  subdirectory, so every run reported "Extract failed!" over a copy PowerShell
  called successful. The destination is named explicitly now, and
  `test_windows_installer_extract.py` rebuilds the generated PowerShell and runs
  it against a staged zip rather than trusting the batch file's own wording.
- **The Windows installer installs every declared dependency.** Its hard-coded
  list named five packages and omitted `bcrypt`, so ACL commands raised
  `ImportError` on any machine installed that way.
- **Both installers install the project** (`pip install <project dir>`) instead of
  running `main.py` from a source tree, so `cm` is a real console script and
  packaging problems surface at install time.
- Both installers take a scripted path (`cm.sh --yes`, `cm_for-windows.bat /Y`)
  and verify the result: console script present, dependencies import, `cm
  --version` and `cm --help` succeed, node agent and `core/__init__.py` intact.
  `--verify-only` / `/VERIFYONLY` re-runs just the checks.
- Both accept `CM_SOURCE_DIR` / `--source=` to install from a checkout instead of
  downloading `main`, which is how CI verifies a branch under test.
- Temp files moved to `mktemp` instead of a fixed world-writable `/tmp` path.
- **An update keeps the keys an existing install already has.** Moving the
  package to `$INSTALL_DIR/project/cloudmesh` left the update path looking for
  `.node_keys.json` only in the new location, and staging clears the project
  directory, which takes `.secret.key` with it — either loss makes every stored
  password and node auth key undecryptable. The update path now backs up both
  files from either layout and restores them after staging.

### Added — verification

- **CI runs on Linux and Windows.** `lint` (ruff `F821`/`F823`/`E9`/`F811`,
  LF-ending check, shellcheck), `test` (4 Python versions x 2 OSes), and
  `installed-cli`, which builds the wheel, installs it into a clean venv, and
  walks every command path asking for `--help`.
- **New `installers.yml` workflow** installs from the checkout on each platform and
  asserts the result works. Neither installer could be verified before, because
  both were interactive-only.
- **New `release.yml` workflow** builds and attaches artifacts on a version tag.
  The release notes are cut from this file by `scripts/release_notes.py`, which
  strips the tag's leading `v` before matching the `## [3.5.0]` heading — the
  inline match it replaces compared `v3.5.0` against a heading that carries no
  `v`, so it never matched and an empty section fell back to "See CHANGELOG.md".
  A missing section now fails the job instead, and
  `cloudmesh/tests/test_release_notes.py` verifies the extraction against this
  file.
- `scripts/smoke_cli.py` walks the whole command surface (286 paths) against
  whatever `cm` is on `PATH`, so it verifies an installed release. It found 119
  of them before the walker stopped mistaking option choices for subcommands.
- `cloudmesh/tests/test_installers.py` pins the installer contracts above.
- `test_cli_regressions.py`, `test_cli_no_tracebacks.py`, and
  `test_panic_rotation.py` cover the dispatch, first-use, and key-rotation bugs.
- **Static analysis, dependency audit, and secret scanning run in CI.** `bandit`
  reports without gating while its findings are triaged, `pip-audit` is a hard
  gate, and `gitleaks` scans the full commit history rather than a shallow
  clone.
- **Release metadata guards.** The advertised version, command count, and test
  count are derived from `pyproject.toml`, the real parser, and a collection-only
  pytest run, then compared. The README had claimed 206 tests against a suite of
  826 and 155 commands against a parser exposing 286, and nothing failed because
  the badges are not built from anything. The CHANGELOG's own structure is held
  to the same standard, because this release was written under two `[Unreleased]`
  headings at once and numbered `3.5.2` without a `3.5.0` beneath it.

### Added

- **`cm` checks for Git everywhere it is needed, and names what depends on it.**
  `cm update` is git-based (`fetch` + `rev-list` + `pull`) and so is pushing your
  own work, but nothing said so: neither installer looked for git, `cm doctor`
  had no row for it, and the failure only surfaced as `Update failed: [Errno 2]
  No such file or directory: 'git'`. Both installers now detect git and offer to
  install it (declining continues the install and points at `pip`), `cm doctor`
  gains `Git` and `Update path` rows, `cm update` auto-detects with `--git` and
  `--pip`, and `cloudmesh/core/git_support.py` centralises detection so a missing
  git is a reported state rather than an exception.
- **Property-based fuzzing of argument parsing** (Hypothesis): no argument vector
  may produce an uncaught traceback, and no path may crash storage resolution.
- **The website's command reference is held to the real parser, and its version
  claim to `pyproject.toml`**, so the site cannot become a third place
  advertising a command — or a release — the CLI is not.
- **Scroll reveals on the site**, with the base rule keeping content visible so a
  reduced-motion reader never gets content stuck at the start of an animation.

### Changed

- The dispatch destination is `cmd_name`; handlers read the command to run from
  `args.command` as before.
- README, `CONTRIBUTING.md`, and the badges now state 286 command paths, and the
  Python floor is stated as 3.10+, matching `requires-python`.
- Duplicated README badges (`Tests`, `Website`, `License`) removed; a duplicated
  figure is a second thing to forget to update.

## [3.4.0] - 2026-10-05 — Enterprise (stable)

This is the Enterprise stable release: SQLite is the source of truth for all
operational data, every CLI command is smoke-tested, and the suite holds
206 passed / 1 skipped with the 25% coverage gate at ~40%.

### Added
- **Smart diagnostics**: `cm diagnose` inspects resources, SSL expiries,
  watcher alerts, backup freshness, and drift, then prints severity-ranked
  findings with fix suggestions (`--json` for scripting, exit 2 on critical).
- **Drift detection**: `cm drift snapshot` records a baseline of managed
  state (servers, nodes, groups, schedules, templates, aliases, alert rules,
  never secrets); `cm drift check` reports added/removed/modified entries
  (exit 1 on drift); `cm drift list/clear` manage the baseline.

### Fixed
- **Broken command groups repaired**: `cm docker`, `cm firewall`, `cm ssl`,
  and `cm logagg` called Manager classes that did not exist in their modules
  (every invocation died with `ImportError`). Thin adapter classes
  (`DockerManager`, `FirewallManager`, `SSLChecker`, `LogAggregator`) now map
  the CLI onto the existing function APIs, including UFW rule parsing,
  SSL history/renewal summaries, and a log-source registry.
- **Standalone node agent boots without `core/`**: `NodeAgent` fell back to
  nothing when `core.ddos` was absent on deployed nodes and crashed on
  startup; it now uses an embedded rate-limit/ban fallback with the same
  interface.
- **Import sweep test**: `test_main_absolute_imports_resolve` fails the suite
  if any `from cloudmesh.* import` in `main.py` stops resolving.

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