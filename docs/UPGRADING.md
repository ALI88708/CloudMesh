# Upgrading to CloudMesh 4.1.2 LTS

This guide covers the real published upgrade path: **3.4.0 to 4.1.2**.
`4.0.0` was an internal development checkpoint and has no tag or published
artifact. `4.1.2` is the first published 4.x release and the supported LTS.

## Before you start

1. Stop scheduled jobs, watchers, tunnels, and the API.
2. Back up the configuration and SQLite state:

   ```bash
   cm config export --output ./cloudmesh-backup-4.1.2
   cm storage backup
   ```

3. Keep the exported directory and the backup file outside the CloudMesh
   installation directory.
4. Confirm the controller runs **Python 3.11 or newer**. Python 3.10 is no
   longer supported; installation is refused by `Requires-Python`.

### 3.4.0 does not read `CLOUDMESH_DIR`

`CLOUDMESH_DIR` was introduced after 3.4.0. A 3.4.0 install ignores the
variable entirely and keeps every piece of state — `config.json`,
`cloudmesh.db`, `.secret.key` — inside its own installation directory
(`.../site-packages/cloudmesh/`).

4.1.2 does read it. So if the variable is set while you upgrade, 4.1.2 looks
in the directory the variable points at, finds nothing, and reports:

```text
No servers configured.
```

The servers are not lost; they are still in the 3.4.0 install directory.

**Do not set `CLOUDMESH_DIR` for the upgrade itself.** Upgrade with the
variable unset, confirm your servers are back with `cm server list`, and only
then move the state to a directory of your choosing and set the variable.

To move a 3.4.0 install to an explicit directory, copy the state files
yourself:

```bash
cp <site-packages>/cloudmesh/config.json <site-packages>/cloudmesh/cloudmesh.db \
   <site-packages>/cloudmesh/.secret.key "$CLOUDMESH_DIR"/
```

The three files travel together: `config.json` is encrypted with
`.secret.key`, and the server list lives in `cloudmesh.db`.

## Install 4.1.2

CloudMesh is distributed through GitHub Releases, not PyPI. The `cloudmesh`
name on PyPI belongs to a different project.

```bash
pip install https://github.com/ALI88708/CloudMesh/releases/download/v4.1.2/cloudmesh-4.1.2-py3-none-any.whl
cm --version
```

From a source checkout:

```bash
pip install .
```

The release also publishes `SHA256SUMS`. To verify a downloaded wheel:

```bash
curl -LO https://github.com/ALI88708/CloudMesh/releases/download/v4.1.2/SHA256SUMS
sha256sum -c SHA256SUMS --ignore-missing
```

## What changes

### Python 3.11+

Python 3.10 is end-of-life and is not supported by the LTS line. Upgrade the
interpreter before upgrading CloudMesh.

### API exec is opt-in

`/api/exec` is disabled by default, even with a valid API key. The read-only
endpoints (`/api/status`, `/api/servers`, `/api/nodes`, `/api/health`) still
work.

To enable remote command execution:

```bash
cm api --enable-exec
```

To allow only exact commands:

```bash
cm api --enable-exec --allow-command "uptime" --allow-command "df -h"
```

The API stays on `127.0.0.1`. For remote use, forward the port over SSH; do not
expose it directly.

### API keys are per-run

A generated key is printed once at startup and is not written to disk. For
automation, create a key file with owner-only permissions and pass it
explicitly:

```bash
# POSIX
umask 077
python -c "import secrets; print(secrets.token_hex(32))" > ~/.cloudmesh-api-key
chmod 600 ~/.cloudmesh-api-key
cm api --api-key-file ~/.cloudmesh-api-key
```

`cm api` refuses a POSIX key file that is group- or world-readable.

### `cm update` uses verified GitHub releases

`cm update --pip` downloads the matching 4.1.x wheel and `SHA256SUMS` from
GitHub, verifies the digest, and installs the local wheel. It never falls back
to the PyPI `cloudmesh` package. `cm update --git` remains a developer path for
a source checkout and tracks `main`; it is not the LTS channel.

### Command ledger rotation

`cm cmdlog --verify` now continues to report a valid chain after the
500-entry rotation. A checkpoint records the last dropped hash. Editing the
retained first entry or the checkpoint is still detected.

### Database credential files

Remote MySQL and PostgreSQL credential files are created with `mktemp`,
`umask 077`, and a cleanup trap. There is no predictable `/tmp` path.

## Verify the upgrade

```bash
cm doctor
cm server list
cm cmdlog --verify
cm storage list
cm migrate --verify
```

The `cm doctor` output should show the expected storage, key, and permission
checks. A permission failure includes the `chmod 600` remediation command.

`cm migrate --verify` compares the JSON mirror against SQLite and prints
`Verify: OK` when they agree. This is the check to run after an upgrade — it
is read-only and it never writes.

Do **not** run `cm migrate` (the write mode) as an upgrade step. A 3.4.0
install already holds its servers in SQLite, so the write mode tries to insert
rows that are already there and reports:

```text
Errors: 1
  - Failed to migrate server <name>: storage rejected server (duplicate or constraint)
Success: False
```

That message describes an already-migrated row, not a failed upgrade. The
state is correct and `cm migrate --verify` confirms it. (`cm storage` has no
`migrate` subcommand — the migration check is the top-level `cm migrate`.)

## Rollback

There is no in-place data downgrade. To roll back:

1. Uninstall 4.1.2:

   ```bash
   pip uninstall -y cloudmesh
   ```

2. Reinstall the 3.4.0 wheel.
3. Restore the pre-upgrade configuration:

   ```bash
   cm config import ./cloudmesh-backup-4.1.2
   cm server list
   ```

4. Restore the SQLite backup only if the 3.4.0 build supports the same storage
   backend. Otherwise keep the backup for a later re-upgrade and use the
   exported configuration for the rollback.

### What `cm config import` does and does not restore in 3.4.0

`cm config export` and `cm config import` in 3.4.0 copy a fixed list of
files: `.secret.key`, `alerts.json`, `.node_keys.json`, the `data/` JSON
files, and the profiles directory. Two limits were confirmed by the drill:

- **The server list is not in that list.** In 3.4.0 the servers live in
  `cloudmesh.db`, and neither the export nor the import touches that file.
- **The import only overwrites files that already exist.** On a fresh 3.4.0
  install, `cm config import` reports `Imported 0 config file(s)` and creates
  nothing.

In practice the servers still come back after a rollback in the same virtual
environment, because `pip uninstall` removes the code but leaves the state
files (`config.json`, `cloudmesh.db`, `.secret.key`) in the installation
directory, and 3.4.0 reads them from there.

When the rollback lands on a **fresh** 3.4.0 install — a new virtual
environment, a new machine, or a directory that was cleared — copy the state
files across by hand:

```bash
cp <backup>/config.json <backup>/cloudmesh.db <backup>/.secret.key \
   <site-packages>/cloudmesh/
cm server list
```

Copy all three together. `config.json` is encrypted with `.secret.key`, and
the server list is in `cloudmesh.db`. The `cm config export` directory is not
a substitute: it does not contain `config.json` or `cloudmesh.db`.

`cm storage backup` (4.1.2) does copy `cloudmesh.db`, and that backup is the
file to keep if you expect to roll back to a fresh 3.4.0 install.

## Upgrade drill record

This path was exercised end to end on Windows, from a 3.4.0 tag build in a
separate virtual environment, against the 4.1.2 wheel. The commands and their
results:

| Step | Command | Result |
| --- | --- | --- |
| Baseline | `pip install <3.4.0 source>` | `CloudMesh 3.4.0` |
| State | `cm server add -n drill -H 127.0.0.1 -u root` | `drill` listed; state written to the install directory, `CLOUDMESH_DIR` ignored |
| Export | `cm config export --output <backup>` | `Exported 2 config file(s)` — `.secret.key` and `alerts.json` only; no `config.json`, no `cloudmesh.db` |
| Upgrade | `pip install --upgrade cloudmesh-4.1.2-py3-none-any.whl` | `CloudMesh 4.1.2` |
| Servers | `cm server list` | `drill` still listed |
| Migration | `cm migrate --verify` | `Verify: OK`, all eight types `match` |
| Health | `cm doctor` | every storage, key, and permission row `PASS` |
| Rollback | `pip uninstall -y cloudmesh` then `pip install <3.4.0 source>` | `CloudMesh 3.4.0` |
| Restore | `cm config import <backup>` | `Restored secret_key`, `Restored alerts` — `drill` still listed, because `cloudmesh.db` survived the uninstall in the install directory |
| Fresh 3.4.0 | `cm config import <backup>` on an empty install | `Imported 0 config file(s)`, `No servers configured.` — the import cannot create missing files and does not carry `cloudmesh.db` |
| Fresh recovery | copy `config.json`, `cloudmesh.db`, `.secret.key` into the 3.4.0 install directory | `drill` listed again |

The two behaviours that are easy to get wrong are the `CLOUDMESH_DIR` switch
and the `cm config import` limits described above.

## Getting help

- Security issues: follow `SECURITY.md`; do not open a public issue for a
  suspected P0 or P1.
- LTS scope and support dates: `docs/LTS.md`.
- Release assets and checksums: the GitHub release page for `v4.1.2`.
