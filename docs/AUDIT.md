# CloudMesh 4.1.2 LTS hardening audit

Date: 2026-10-20

This is an internal code and regression audit. It is not a third-party
certification or a penetration test of a deployed host.

## Fixed

| # | Finding | Fix |
|---|---------|-----|
| 1 | Profile snapshots wrote decrypted server configuration, including passwords, to `cloudmesh/.profiles/*.json`. Profile names were joined into paths without validation, so `../name` escaped the directory. | Profiles are Fernet-encrypted with the same key as `config.json`, written atomically with mode `0600` where the OS supports it, and names are restricted to `[A-Za-z0-9_.-]`. Existing plaintext profiles are still readable for migration. |
| 2 | `database`, `docker`, `firewall`, `logagg`, `reshistory`, and `watcher` read a legacy `data/cloudmesh.json` that the SQLite manager no longer creates. They reported “server not found” after `cm server add` and expected `key` while storage returns `key_path`. | `core/server_config.py` builds the legacy view from SQLite, aliases `key_path` to `key`, and falls back to an existing JSON file. Legacy modules delegate to it. |
| 3 | `CLOUDMESH_DIR` moved the database and encryption key but left node keys, profiles, schedules, templates, notifications, checkpoints, job files, panic state, aliases, service files, and feature JSON in the installed package. | `core/paths.py` is the shared resolver. The affected modules and `main.py` now use it, so a sandbox relocates all state together. |
| 4 | `DirectorySync.sync_from` trusted the remote `find` listing. A malicious or compromised server could return `../../path` or an absolute path and make the controller write outside the destination. | Remote paths are resolved under the destination root and rejected with an `Unsafe remote path` result otherwise. |
| 5 | `NodeClient` read a 4-byte length and then accumulated that many bytes without a limit, allowing a hostile node to exhaust controller memory. | Responses larger than 50 MiB are rejected before allocation. |
| 6 | The REST API leaked a per-IP connection slot whenever a handler raised, and `stop()` only flipped a flag. The listening socket stayed bound after `cm api` exited. | Handler work is wrapped in `try/finally` for slot release. `stop()` shuts down and closes the server, and the reported port is the bound ephemeral port. |
| 7 | Shell metacharacters in log search patterns, watcher process names, Docker container names, image names, environment values, compose paths, PostgreSQL host/user and passfile fields, and MySQL option-file values could break out of the remote command or inject config directives. | Values are quoted with `shlex.quote` or escaped for the target config format. Docker image, deployment container, port, and environment-variable names are allowlisted; ad-hoc container arguments are shell-quoted. |
| 8 | `cm node install` uploaded to the predictable `/tmp/node-install.sh` and ran it with `bash`, which is absent on FreeBSD and minimal Linux. | The installer uses `mktemp`, a unique remote path, `sh` (the script's actual interpreter), and removes both local and remote temporary files. |
| 9 | A valid API key could call `/api/exec`; the dangerous-command blocklist was the only control. String matching is bypassable, so a leaked key meant remote command execution. | `/api/exec` is disabled by default. The operator must pass `cm api --enable-exec`; `--allow-command` restricts execution to exact command strings. The API remains loopback-only. |
| 10 | `cm api` generated a key per run and printed it only to the terminal, so automation had no supported key source. | Generated keys stay per-run and are never persisted. Automation uses `--api-key-file`; on POSIX the file must be mode `0600`. |
| 11 | Remote MySQL and PostgreSQL helper files used fixed `/tmp/.cm_my.conf` and `/tmp/.cm_pgpass` paths, so a hostile local account could race them. | Each command uses `mktemp`, `umask 077`, `chmod 600`, and an `EXIT HUP INT TERM` cleanup trap. A failed `mktemp` aborts rather than falling back to a predictable path. |

## Regression coverage

`cloudmesh/tests/test_hardening.py` covers each item above:

- profile encryption, traversal rejection, legacy plaintext, and sandbox path;
- SQLite-to-legacy server lookup for all six modules, key alias, and JSON fallback;
- `CLOUDMESH_DIR` for feature data and state managers;
- node-key and profile paths;
- oversized node responses;
- sync path containment;
- log and watcher quoting;
- Docker deploy validation/quoting;
- PostgreSQL and MySQL quoting;
- node installer path and interpreter;
- API shutdown and port release.

Run the suite with:

```bash
python -m pytest cloudmesh/tests -q
```

## Accepted risks

- **REST API is loopback-only HTTP.** The API has no external-bind flag and is
  not a TLS terminator. A local process that obtains the key can call it, and a
  local observer can read loopback traffic. Remote use is through an SSH tunnel;
  adding public bind or TLS is out of scope for `4.1.x`.
- **`/api/exec` is an operator feature, not a sandbox.** It is opt-in and can be
  restricted with `--allow-command`, but an enabled unrestricted exec endpoint
  intentionally runs the operator's command. The container, image, and
  deployment inputs are quoted or validated; the command itself is an operator
  instruction.
- **`docker exec` passes the operator's command through.** This is the feature,
  not an injection. The container and deployment are the trust boundary.
- **The node protocol is unchanged.** Shared auth keys, optional TLS, optional
  SPA, and no replay cache remain. Use TLS; a protocol change is deferred to a
  feature line.
- **`cm api` prints a generated key to the terminal.** That is intentional
  bootstrap behaviour; treat the terminal output as sensitive. Automation uses
  `--api-key-file` instead.
