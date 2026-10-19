# CloudMesh 4.0.0 — BSD Family Support

**Status:** Draft for approval
**Date:** 2026-10-19
**Target release:** CloudMesh 4.0.0 (3.5.0 shipped 2026-10-16)
**Branch:** `feature/bsd-support` (based on `fix/3.5.0-release-prep` @ `91897ec`)

---

## 1. Why

CloudMesh's promise is one CLI over every server its user owns. Today that promise
stops at Linux and Windows. The BSD family — FreeBSD, OpenBSD, NetBSD — runs a large
share of the internet's servers and network appliances: hosting, routers and firewalls,
NAS boxes, mail and DNS infrastructure. Those machines are invisible to CloudMesh
today, and a BSD operator cannot run the controller at all.

4.0.0 extends the pool in both directions:

- a BSD machine can join as a managed **server** (SSH) and as a **node** (agent);
- the CloudMesh **controller** itself installs and runs on BSD.

## 2. Goals

**G1 — Manage BSD machines.** The node agent installs and runs on FreeBSD, OpenBSD
and NetBSD. Controller commands work end-to-end for the core workflows: monitoring,
command execution, file transfer and directory sync, async jobs, logs, package
deployment, firewall, security audit, dashboards.

**G2 — Controller on BSD.** `cm` installs and runs on FreeBSD (primary), plus
OpenBSD/NetBSD as best effort, including local monitoring, `cm doctor` and
`cm service`.

**G3 — One OS-profile layer.** Every OS-specific command and parser lives in one
module. Linux and Windows move onto it with identical behaviour. Adding an OS later
is additive, not a refactor.

**G4 — Zero regressions.** Linux and Windows behaviour does not change. The full
test suite stays green. Every new behaviour is written test-first.

**G5 — Ship 4.0.0.** Version bump, BSD classifiers, README support matrix,
CONTRIBUTING notes, CHANGELOG entry.

## 3. Non-goals (4.0.0)

- **Docker on BSD** — Docker does not run natively on BSD. Jails and podman are a
  separate feature. Docker commands return an explicit "not supported on this OS"
  message instead of a command-not-found failure.
- **GPU beyond `nvidia-smi`** — telemetry only where `nvidia-smi` exists (FreeBSD
  with the vendor driver). Everywhere else the value is reported as unavailable.
- **macOS** — out of scope; existing classification and behaviour stay untouched.
- **BSD-specific administration** — jails, ZFS dataset management, ports tree
  management, bhyve. Out of scope.
- **Windows node changes** — untouched.
- **SPA (Ghost Ports) on BSD** — Linux-only in 4.0.0. `--spa` on a BSD node fails
  closed with a clear "SPA is not supported on this OS yet" message. A pf-based
  SPA backend is a stretch item, not an acceptance criterion.
- **Storage migration** — `servers.os_type` is already free text; no schema change.

## 4. Anti-goals

- No per-OS forks of modules, and no scattered `if os_type == ...` inside feature
  modules. OS decisions belong to the profile layer.
- No silent degradation. A feature that cannot work on an OS returns a clear,
  tested message.
- The node agent stays a standalone single file: stdlib plus optional psutil, no
  imports from the controller package.
- No unquoted shell interpolation of user input; keep the `shlex.quote` discipline.
- No behaviour changes on Linux/Windows for the sake of uniformity.

## 5. Constraints

- Python ≥ 3.10; no new mandatory dependencies; the agent keeps psutil optional.
- TDD: failing test first, then the smallest change, then refactor.
- Development and the test suite run on Windows; new unit tests must not require a
  BSD host.
- FreeBSD 14.x is the reference platform. OpenBSD and NetBSD go through the same
  profile layer and are unit-tested; live-host verification is best effort.
- End-to-end acceptance needs a BSD host or VM. Availability is an open question.
- 3.5.0 shipped on 2026-10-16; 4.0.0 is the next release.

## 6. Fixed decisions (yours)

- Support the BSD **family**, not a single member: FreeBSD, OpenBSD, NetBSD.
- Ship it as **4.0.0**, the next major release.
- Planning first, then implementation, with tests first.

## 7. Calls I am making (vetoable)

**C1 — Scope priority.** Both directions ship in 4.0.0. BSD-as-managed-machines
comes first; controller-on-BSD comes second.

**C2 — Family depth.** FreeBSD is the reference platform with full depth. OpenBSD
and NetBSD are implemented through the same profiles and covered by unit tests;
their live end-to-end verification is best effort.

**C3 — Profile module.** New `cloudmesh/core/osprofile.py` with one profile class per
OS (strategy pattern), a shared BSD base class, and `get_profile(os_type)` that never
raises. Unknown or legacy values fall back to the current Linux behaviour.

**C4 — Detection.** `detect_os` maps `uname -s`: Linux → `linux`, FreeBSD →
`freebsd`, OpenBSD → `openbsd`, NetBSD → `netbsd`. Darwin keeps today's `linux`
classification to avoid a behaviour change. The Windows fallback is unchanged.

**C5 — Storage.** No migration. `servers.os_type` accepts the new values; validation
happens in code.

**C6 — Remote command policy.** BSD commands use base-system tools (`sysctl`,
`vmstat`, `df`, `ps`, `ifconfig`, `md5`, `pkg`/`pkg_add`) and are parsed in the
controller. SSH-only BSD servers must not gain a Python requirement. Linux commands
stay as they are.

**C7 — Firewall.** A pf backend covers status, list, add, remove and check-port on
FreeBSD, OpenBSD and NetBSD when pf is enabled. FreeBSD's ipfw is detect/status/list
only. Anything else returns an explicit "no supported firewall detected" message.

**C8 — Packages.** FreeBSD uses `pkg`, OpenBSD and NetBSD use `pkg_add`. Privilege
escalation uses `sudo` when present, otherwise `doas`. psutil is installed from the
OS package repository first, with pip as fallback.

**C9 — Sync fingerprint.** The remote MD5 command comes from the profile:
`md5 -q` on BSD, `md5sum` on Linux.

**C10 — Logs.** Default log paths come from the profile
(`/var/log/messages`, per-OS auth logs, and the existing discovery paths).

**C11 — Audit.** Per-OS check lists. The hardcoded `systemctl` row is Linux-only and
must not appear on BSD.

**C12 — Agent.** A small `platform.system()` shim inside the standalone agent.
Metrics stay psutil-first with sysctl fallbacks. The safe-write path uses
`/proc/self/fd` only when it exists. SPA stays Linux-only with a clear fail-closed
message; the pf SPA backend is a stretch item.

**C13 — Services.** Native rc.d units per BSD family, generated and enabled by the
installer. `cm service` is pid-file based and already OS-neutral; it stays unchanged.

**C14 — Installers.** One OS-aware `node-install.sh` with POSIX-safe helpers, plus a
new `cm_for-bsd.sh` for the controller. The Linux and Windows installers keep working.

**C15 — Release.** Version 4.0.0, BSD classifiers, README support matrix, CHANGELOG,
CONTRIBUTING.

## 8. Architecture

### 8.1 Controller: the OS profile layer

`cloudmesh/core/osprofile.py` defines a small protocol:

- identity: `key` (`linux`, `windows`, `freebsd`, `openbsd`, `netbsd`), `family`;
- command builders: `cpu_cmd()`, `ram_cmd()`, `disk_cmd()`, `uptime_cmd()`,
  `top_cmd(sort_by)`, `network_cmd()`, `who_cmd()`;
- file and package helpers: `log_paths()`, `md5_cmd(path)`, `package_manager()`,
  `package_install_cmd(package)`, `package_detect_cmd(package)`;
- security: `audit_checks()`, `firewall_backend()`.

Concrete profiles: `LinuxProfile`, `WindowsProfile`, and a `BsdProfile` base with
`FreeBsdProfile`, `OpenBsdProfile` and `NetBsdProfile`. Parsers live next to the
commands they parse; presentation stays in the feature modules.

`get_profile(os_type)` never raises: unknown or legacy values return the Linux
profile, which is exactly today's behaviour.

### 8.2 Detection and storage

`ServerManager.detect_os` runs `uname -s` and maps the result. The new values are
stored in the existing `os_type` field. Existing stored configs keep working because
the fallback is Linux.

### 8.3 Remote command policy

Commands are POSIX-quoted. BSD paths do not assume bash: uploaded scripts run with
`sh` on BSD, while Linux keeps `bash`. No new remote dependency is introduced for
SSH-only servers.

### 8.4 Node agent

`cloudmesh_node.py` gains an OS shim derived from `platform.system()`. Metrics stay
psutil-first; sysctl fallbacks cover a missing psutil. `_safe_open_write` only
resolves `/proc/self/fd/<fd>` when that path exists; otherwise it uses the
already-validated real path with `O_NOFOLLOW`. SPA startup reports a clear
unsupported-OS error before touching firewall tooling.

### 8.5 Services and installers

- FreeBSD: rc.d unit under `/usr/local/etc/rc.d/`, launched through `daemon(8)`.
- OpenBSD: `/etc/rc.d/` unit managed with `rcctl`.
- NetBSD: `/etc/rc.d/` unit with `run_rc_command`.
- Helper scripts (`start.sh`, `stop.sh`, `status.sh`, `restart.sh`) use `#!/bin/sh`.
- IP detection no longer relies on Linux-only `hostname -I`.
- Controller installer `cm_for-bsd.sh` mirrors the Linux installer and supports the
  same verify-only flow.

### 8.6 CLI behaviour

Command names and flags do not change. Monitoring, dashboard, weather, trust and
resource history inherit BSD support through the profile layer. Docker commands
return an explicit unsupported message on BSD. `cm doctor` gains OS-aware local
checks.

### 8.7 Impact map

| Area | Change |
| --- | --- |
| `cloudmesh/core/osprofile.py` | New profile layer and parsers |
| `cloudmesh/core/server.py` | `detect_os` mapping |
| `cloudmesh/core/monitor.py` | Commands and parsers from the profile |
| `cloudmesh/core/features.py` | Top, network, who, uptime, log helpers from the profile |
| `cloudmesh/core/reshistory.py` | Snapshot command from the profile |
| `cloudmesh/core/deploy.py` | BSD package managers; `sh` script runner |
| `cloudmesh/core/firewall.py` | pf backend; explicit ipfw limitation |
| `cloudmesh/core/sync.py` | Remote MD5 command from the profile |
| `cloudmesh/core/logagg.py` | Log paths from the profile |
| `cloudmesh/core/advanced.py` | Audit checks from the profile |
| `cloudmesh/core/docker.py` | Explicit unsupported message |
| `cloudmesh/node/cloudmesh_node.py` | OS shim, safe-write fix, SPA message |
| `cloudmesh/node/node-install.sh` | OS-aware install and rc.d units |
| `cm_for-bsd.sh` | New controller installer |
| `pyproject.toml`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md` | Version, classifiers, docs |
| `cloudmesh/tests/*` | New and extended tests |

## 9. Test strategy

Unit tests (no BSD host required):

- profile command builders and parsers, pinned against fixtures;
- `detect_os` mappings with mocked SSH output;
- agent OS mapping, safe-write without `/proc`, SPA fail-closed message;
- deploy, firewall, sync, log aggregation and audit against a mocked execute;
- installer content: rc.d units, package branches, POSIX syntax checks.

Regression: the complete existing suite must stay green.

End-to-end (requires a real host): install the agent on FreeBSD 14, add it to a
controller, then exercise node test/exec/job/upload/download, monitoring, top, disk,
network, who, logs, sync, deploy, firewall status and audit. The same checklist then
runs with the controller installed on FreeBSD.

## 10. Acceptance criteria

- [ ] FreeBSD 14 node: installer succeeds, rc.d service starts on boot, `cm node test`
      reports online, exec/job/upload/download work.
- [ ] FreeBSD 14 controller: `cm --help`, `cm node`, `cm mon --local`,
      `cm service start/status/stop` and `cm doctor` work.
- [ ] Monitoring, top, disk, network, who, logs, sync, deploy, firewall and audit
      return real data on FreeBSD.
- [ ] OpenBSD and NetBSD: profiles and parsers covered by unit tests; live checks
      documented as best effort.
- [ ] Linux and Windows: full suite green, no behaviour change.
- [ ] `cm --version` reports 4.0.0; README, CHANGELOG and CONTRIBUTING updated.

## 11. Risks and unknowns

- **No BSD host yet.** The biggest unknown. Without one, acceptance criteria 1–3 are
  verified only by mocked tests, and the release would carry unverified BSD paths.
- **Binary wheels on BSD.** `psutil` and `cryptography` may be built from source by
  pip; the installers must prefer OS packages.
- **Package name drift.** OpenBSD and NetBSD Python/psutil package names differ by
  release; the installer needs a small candidate list.
- **Firewall defaults.** pf is enabled by default on OpenBSD but not on FreeBSD or
  NetBSD; the backend must detect the actual state, not assume it.
- **rc.d environment.** `PATH` under rc.d may not include `/usr/local/bin`; units
  must set it explicitly.
- **bash absence.** `deploy.run_script` currently runs `bash`; BSD needs `sh`.
- **Release bookkeeping.** 3.5.0 has a CHANGELOG entry but no local git tag; the
  release step must confirm the tag state before publishing 4.0.0.

## 12. Questions for you

1. **BSD host.** Do we have a FreeBSD (or any BSD) host/VM we can use today? If not,
   is a mocked-test-only 4.0.0 acceptable, with end-to-end verification as a release
   blocker?
2. **Priority.** Confirm BSD-as-managed-machines first, controller second, with
   OpenBSD/NetBSD as best effort.
3. **SPA.** Stretch item (recommended), or must-have for 4.0.0?

## 13. Left to the plan

- Exact BSD command strings and parsers, pinned by fixtures and TDD.
- Exact rc.d unit contents and package names per BSD release.
- File-by-file task breakdown, order and estimates.
- Release and tagging steps.
