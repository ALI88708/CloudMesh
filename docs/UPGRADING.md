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
```

The `cm doctor` output should show the expected storage, key, and permission
checks. A permission failure includes the `chmod 600` remediation command.

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

## Getting help

- Security issues: follow `SECURITY.md`; do not open a public issue for a
  suspected P0 or P1.
- LTS scope and support dates: `docs/LTS.md`.
- Release assets and checksums: the GitHub release page for `v4.1.2`.
