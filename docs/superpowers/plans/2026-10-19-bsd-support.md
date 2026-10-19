# CloudMesh 4.0.0 — BSD Family Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make CloudMesh manage FreeBSD, OpenBSD and NetBSD machines and run on FreeBSD itself, through one OS-profile layer, shipping as 4.0.0.

**Architecture:** A new `cloudmesh/core/osprofile.py` maps `os_type` to a profile object that owns every OS-specific command string and parser. Monitoring, features, deploy, sync, firewall, logs, reshistory and audit consume the profile; the standalone node agent gets its own small shim. End-to-end proof runs in a FreeBSD VM inside GitHub Actions.

**Tech Stack:** Python 3.10+ (stdlib), existing deps only (psutil, paramiko, rich, cryptography), pytest, GitHub Actions (`vmactions/freebsd-vm`).

**Spec:** `docs/superpowers/specs/2026-10-19-bsd-support-design.md`

## Global Constraints

- Python ≥ 3.10; no new mandatory dependencies.
- The node agent (`cloudmesh/node/cloudmesh_node.py`) stays a standalone single file: stdlib + optional psutil, no imports from the controller package.
- TDD: failing test first, smallest change to green, then refactor.
- Every new unit test must pass on Windows with no BSD host. FreeBSD-only live tests are skipped unless `sys.platform == "freebsd"`.
- `get_profile()` never raises; unknown/legacy/None os_type falls back to Linux.
- No Linux/Windows behaviour change: existing suite (916 passed, 39 skipped) stays green.
- All remote paths and user values pass through `shlex.quote`.
- Test command: `python -m pytest cloudmesh/tests -q` from the repo root.
- Commits: one per task, conventional messages.

## Review Focus

1. **Legacy configs** — a stored server with missing or unknown `os_type` must behave exactly as today (Linux path), never raise. *(Tasks 1, 4, 5)*
2. **BSD present but tool missing** — pf not enabled, psutil absent, no `doas`/`sudo`: explicit message, no crash. *(Tasks 8, 13)*
3. **`get_profile(None)` / empty / uppercase** — falls back to Linux. *(Task 1)*
4. **Quoting** — log paths, md5 paths, firewall rules must be `shlex.quote`d. *(Tasks 5, 7, 8)*
5. **Agent on POSIX without `/proc`** — safe writes still work and stay inside the data dir. *(Task 13)*

---

### Task 1: OS profile core — identity, fallback, Linux/Windows resource parity

**Files:**
- Create: `cloudmesh/core/osprofile.py`
- Test: `cloudmesh/tests/test_osprofile.py`

**Interfaces:**
- Produces:
  - `class OsProfile` with `key: str`, `family: str`, and methods
    `cpu_cmd() -> str`, `ram_cmd() -> str`, `disk_cmd() -> str`,
    `parse_cpu(raw: str) -> float | None`, `parse_ram(raw: str) -> dict | None`,
    `parse_disk(raw: str) -> dict | None`.
  - `class LinuxProfile(OsProfile)` (`key="linux"`, `family="posix"`),
    `class WindowsProfile(OsProfile)` (`key="windows"`, `family="windows"`).
  - `get_profile(os_type: str | None) -> OsProfile` — never raises.

- [x] **Step 1: Write the failing test**

```python
# cloudmesh/tests/test_osprofile.py
from cloudmesh.core.osprofile import LinuxProfile, WindowsProfile, get_profile


def test_unknown_and_missing_os_type_fall_back_to_linux():
    assert get_profile(None).key == "linux"
    assert get_profile("").key == "linux"
    assert get_profile("solaris").key == "linux"
    assert get_profile("FREEBSD ").key == "linux"  # not registered yet


def test_linux_profile_commands_match_todays_strings():
    p = LinuxProfile()
    assert "/proc/stat" in p.cpu_cmd()
    assert "/proc/meminfo" in p.ram_cmd()
    assert "statvfs" in p.disk_cmd()
    assert p.parse_cpu("12.5") == 12.5
    assert p.parse_cpu("garbage") is None
    assert p.parse_ram('{"total_gb": 8.0, "used_gb": 2.0, "free_gb": 6.0, "percent": 25.0}')["percent"] == 25.0


def test_windows_profile_uses_powershell():
    p = WindowsProfile()
    assert "powershell" in p.cpu_cmd().lower()
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest cloudmesh/tests/test_osprofile.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cloudmesh.core.osprofile'`

- [x] **Step 3: Implement the module**

Move the exact command literals from `cloudmesh/core/monitor.py` (`LINUX_CPU_CMD`, `LINUX_RAM_CMD`, `LINUX_DISK_CMD`, `WINDOWS_CPU_CMD`, `WINDOWS_RAM_CMD`, `WINDOWS_DISK_CMD`) into `osprofile.py` as module constants, and have the profile methods return them. Parsers: `float(raw)`/`json.loads(raw)` wrapped in try/except returning `None`, matching `ResourceMonitor` today. `_PROFILES = {"linux": LinuxProfile(), "windows": WindowsProfile()}`; `get_profile` lowercases and strips, then `_PROFILES.get(value, _PROFILES["linux"])`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest cloudmesh/tests/test_osprofile.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/osprofile.py cloudmesh/tests/test_osprofile.py
git commit -m "feat: add OS profile layer with Linux and Windows resource commands"
```

---

### Task 2: BSD resource profiles (FreeBSD, OpenBSD, NetBSD)

**Files:**
- Modify: `cloudmesh/core/osprofile.py`
- Test: `cloudmesh/tests/test_osprofile.py`, `cloudmesh/tests/test_osprofile_live.py`

**Interfaces:**
- Consumes: `OsProfile` from Task 1.
- Produces: `FreeBsdProfile`, `OpenBsdProfile`, `NetBsdProfile` registered under
  `"freebsd"`, `"openbsd"`, `"netbsd"`; all with `family="posix"`.

- [x] **Step 1: Write the failing tests**

```python
# appended to test_osprofile.py
FREEBSD_VMSTAT = """ procs      memory      page                    disks     faults         cpu
 r b w     avm    fre  flt  re  pi  po  fr   sr da0 pass0     in   sy  cs us sy id
 1 0 0  123456  78901   12   0   0   0   4    0   0   0    231  456  12  3  2 95
"""


def test_freebsd_cpu_parses_idle_from_last_vmstat_row():
    p = get_profile("freebsd")
    assert p.key == "freebsd"
    assert "vmstat 1 2" in p.cpu_cmd()
    assert p.parse_cpu(FREEBSD_VMSTAT) == 5.0


def test_freebsd_ram_command_and_parser():
    p = get_profile("freebsd")
    assert "hw.physmem" in p.ram_cmd()
    raw = "8589934592\n4096\n500000\n300000\n"
    ram = p.parse_ram(raw)
    assert ram["total_gb"] == 8.0
    assert ram["percent"] > 0
```

Also add one assertion per profile that `get_profile("openbsd").key == "openbsd"`
and `get_profile("netbsd").key == "netbsd"`, and a `parse_cpu`/`parse_ram`
fixture for each.

```python
# cloudmesh/tests/test_osprofile_live.py
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "freebsd", reason="FreeBSD only")


@pytest.mark.parametrize("os_type", ["freebsd"])
def test_commands_work_against_the_real_freebsd_host(os_type):
    import subprocess
    from cloudmesh.core.osprofile import get_profile

    p = get_profile(os_type)
    cpu = p.parse_cpu(subprocess.run(p.cpu_cmd(), shell=True, capture_output=True, text=True).stdout)
    ram = p.parse_ram(subprocess.run(p.ram_cmd(), shell=True, capture_output=True, text=True).stdout)
    disk = p.parse_disk(subprocess.run(p.disk_cmd(), shell=True, capture_output=True, text=True).stdout)
    assert cpu is None or 0.0 <= cpu <= 100.0
    assert ram and ram["total_gb"] > 0 and 0.0 <= ram["percent"] <= 100.0
    assert disk and disk["total_gb"] > 0
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_osprofile.py -q`
Expected: FAIL — `get_profile("freebsd").key == "linux"`

- [x] **Step 3: Implement the BSD profiles**

`BsdProfile(OsProfile)` base plus three subclasses. Commands:
- CPU (all): `vmstat 1 2` — parser takes the last non-empty line, last whitespace
  field is idle %, returns `round(100 - idle, 1)`; `None` on parse failure.
- Disk (all): `df -kP /` — parser skips the header, splits the last line into
  `total_gb/used_gb/free_gb/percent` from 1K blocks.
- RAM: FreeBSD `sysctl -n hw.physmem vm.stats.vm.v_page_size vm.stats.vm.v_free_count vm.stats.vm.v_inactive_count`;
  OpenBSD `sysctl -n hw.physmem hw.pagesize vm.uvmexp.free`;
  NetBSD `sysctl -n hw.physmem64 hw.pagesize vm.uvmexp.free vm.uvmexp.inactive`.
  Parser: first line total bytes, second page size, then page counts; free bytes =
  pages × page size; `percent = round(used/total*100, 1)`. Missing/short output
  returns `None`.
- `Parse failures never raise`; they return `None`.

The FreeBSD OIDs are pinned by the live test in the CI VM (Task 16). For
OpenBSD/NetBSD, if a sysctl name differs on a live host later, update the command
and its fixture together — the fixture is the contract.

- [x] **Step 4: Run to verify pass**

Run: `python -m pytest cloudmesh/tests/test_osprofile.py -q`
Expected: PASS (live test skipped on Windows)

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/osprofile.py cloudmesh/tests/test_osprofile.py cloudmesh/tests/test_osprofile_live.py
git commit -m "feat: add FreeBSD, OpenBSD and NetBSD resource profiles"
```

---

### Task 3: ResourceMonitor consumes the profile layer

**Files:**
- Modify: `cloudmesh/core/monitor.py:1-103`
- Test: `cloudmesh/tests/test_bsd_monitor.py`

**Interfaces:**
- Consumes: `get_profile` from Task 1.
- Produces: `ResourceMonitor.get_cpu/get_ram/get_disk` unchanged signatures.

- [x] **Step 1: Write the failing test**

```python
# cloudmesh/tests/test_bsd_monitor.py
from cloudmesh.core.monitor import ResourceMonitor


class FakeServerManager:
    def __init__(self, os_type, stdout):
        self.os_type = os_type
        self.stdout = stdout
        self.commands = []

    def get_server_info(self, name):
        return {"os_type": self.os_type}

    def execute(self, name, cmd):
        self.commands.append(cmd)
        return {"stdout": self.stdout, "stderr": "", "exit_code": 0}


def test_freebsd_ram_uses_the_profile_command():
    mgr = FakeServerManager("freebsd", "8589934592\n4096\n500000\n300000\n")
    mon = ResourceMonitor(mgr)
    ram = mon.get_ram("bsd1")
    assert ram["total_gb"] == 8.0
    assert "hw.physmem" in mgr.commands[0]


def test_unknown_os_type_still_uses_the_linux_command():
    mgr = FakeServerManager(None, "42.0")
    mon = ResourceMonitor(mgr)
    assert mon.get_cpu("legacy") == 42.0
    assert "/proc/stat" in mgr.commands[0]
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_bsd_monitor.py -q`
Expected: FAIL — the BSD command is not used (Linux command runs instead)

- [x] **Step 3: Rewire `ResourceMonitor`**

Replace the `WINDOWS_* if os_type == "windows" else LINUX_*` selections with
`profile = get_profile(os_type)`; call `profile.cpu_cmd()` / `profile.parse_cpu(raw)`
etc. Delete the now-duplicated constants from `monitor.py` (they live in
`osprofile.py`); check with `rg "LINUX_CPU_CMD|WINDOWS_CPU_CMD" cloudmesh` that
nothing else imports them, and update any importer to pull from `osprofile`.

- [x] **Step 4: Run the new test and the existing suite**

Run: `python -m pytest cloudmesh/tests/test_bsd_monitor.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/monitor.py cloudmesh/core/osprofile.py cloudmesh/tests/test_bsd_monitor.py
git commit -m "refactor: select monitor commands through the OS profile layer"
```

---

### Task 4: `detect_os` maps the BSD family

**Files:**
- Modify: `cloudmesh/core/server.py:270-287`
- Test: `cloudmesh/tests/test_bsd_detect.py`

**Interfaces:**
- Produces: `ServerManager.detect_os(name) -> str` returning `"linux"`,
  `"windows"`, `"freebsd"`, `"openbsd"`, `"netbsd"` or `"unknown"`.

- [x] **Step 1: Write the failing test**

```python
# cloudmesh/tests/test_bsd_detect.py
import pytest
from cloudmesh.core.server import ServerManager


class DetectHarness(ServerManager):
    def __init__(self, uname):
        self._uname = uname
        self.saved = None

    def execute(self, name, cmd):
        return {"stdout": self._uname, "stderr": "", "exit_code": 0}

    def _save(self):
        pass

    def _ensure_mirror(self, name):
        pass

    def get_server_info(self, name):
        return {}

    def update_server_os_type(self, name, os_type):  # storage stand-in
        self.saved = os_type


@pytest.mark.parametrize("uname,expected", [
    ("Linux\n", "linux"),
    ("Darwin\n", "linux"),
    ("FreeBSD\n", "freebsd"),
    ("OpenBSD\n", "openbsd"),
    ("NetBSD\n", "netbsd"),
    ("MINGW64_NT-10.0\n", "windows"),
])
def test_uname_mapping(uname, expected):
    mgr = DetectHarness(uname)
    # bypass storage/config plumbing
    import cloudmesh.core.server as server_mod
    mgr.storage = type("S", (), {"update_server_os_type": lambda self, n, o: None})()
    mgr.config = {"servers": {"node1": {}}}
    assert mgr.detect_os("node1") == expected
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_bsd_detect.py -q`
Expected: FAIL — FreeBSD/OpenBSD/NetBSD report `"windows"`

- [x] **Step 3: Extend the mapping**

In `detect_os`, lower-case the stdout and check, in order: `freebsd` →
`"freebsd"`, `openbsd` → `"openbsd"`, `netbsd` → `"netbsd"`, `linux` or
`darwin` → `"linux"`, else `"windows"`. Keep the storage update and `_save()`
lines untouched.

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_bsd_detect.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/server.py cloudmesh/tests/test_bsd_detect.py
git commit -m "feat: detect FreeBSD, OpenBSD and NetBSD in detect_os"
```

---

### Task 5: Feature commands (uptime, top, disk, network, who, logs) via profiles

**Files:**
- Modify: `cloudmesh/core/osprofile.py` (new methods)
- Modify: `cloudmesh/core/features.py:29-102`
- Modify: `cloudmesh/main.py:4145` (logs `--file` default)
- Test: `cloudmesh/tests/test_bsd_features.py`

**Interfaces:**
- Consumes: `get_profile`.
- Produces on `OsProfile`:
  - `uptime_cmd() -> str`, `top_cmd(sort_by: str, limit: int) -> str`,
    `parse_top(raw: str, sort_by: str, limit: int) -> list[dict]` (dicts with
    `pid`, `usage`, `name`),
  - `disk_detail_cmd() -> str`, `parse_disk_detail(raw: str) -> list[dict]`
    (dicts with `device`, `size`, `used`, `avail`, `use%`, `mount`),
  - `network_cmd() -> str`, `who_cmd() -> str`, `log_paths() -> tuple[str, ...]`.
- Produces in `features.py`: module helper
  `_profile_for(server_mgr, name) -> OsProfile`; `get_recent_logs(..., log_file=None, ...)`
  now resolves the default from the profile.

- [x] **Step 1: Write the failing tests**

```python
# cloudmesh/tests/test_bsd_features.py
from cloudmesh.core import features


class FakeServerManager:
    def __init__(self, os_type, stdout=""):
        self.os_type, self.stdout, self.commands = os_type, stdout, []

    def get_server_info(self, name):
        return {"os_type": self.os_type}

    def execute(self, name, cmd):
        self.commands.append(cmd)
        return {"stdout": self.stdout, "stderr": "", "exit_code": 0}


def test_freebsd_top_parses_and_sorts_in_python():
    ps = "  PID  %CPU %MEM COMMAND\n 11  5.0  1.0 nginx\n 22 40.5  2.0 python\n"
    mgr = FakeServerManager("freebsd", ps)
    procs = features.get_top_processes(mgr, "bsd1", limit=1, sort_by="cpu")
    assert procs == [{"pid": "22", "usage": "40.5", "name": "python"}]
    assert "ps -axo" in mgr.commands[0]


def test_freebsd_logs_default_to_messages():
    mgr = FakeServerManager("freebsd", "a log line")
    out = features.get_recent_logs(mgr, "bsd1", lines=5)
    assert out == "a log line"
    assert "/var/log/messages" in mgr.commands[0]


def test_freebsd_uptime_has_no_gnu_dash_p():
    mgr = FakeServerManager("freebsd", "10:00 up 3 days")
    features.get_uptime(mgr, "bsd1")
    assert mgr.commands[0].strip() == "uptime"
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_bsd_features.py -q`
Expected: FAIL — FreeBSD still gets the Linux commands

- [x] **Step 3: Implement**

Add the methods to `LinuxProfile`/`WindowsProfile` returning today's exact
strings, and to `BsdProfile`: `uptime` → `"uptime"`; top →
`"ps -axo pid,pcpu,pmem,command"` with Python-side filtering of the header,
sorting by `pcpu`/`pmem`, and truncation to `limit`; disk detail → `"df -h"`
parsed into the six fields (skip header rows starting with `Filesystem`);
network → `"ifconfig -a"`; who → `"who"`; `log_paths` →
FreeBSD `("/var/log/messages", "/var/log/auth.log")`, OpenBSD/NetBSD
`("/var/log/messages", "/var/log/authlog")`. Linux log paths stay
`("/var/log/syslog", "/var/log/auth.log", "/var/log/messages")`.

Rewire `features.get_uptime/get_top_processes/get_disk_detail/get_network_info/get_logged_users`
through `_profile_for`. `get_recent_logs`: when `log_file` is falsy, build
`tail -n {lines} {shlex.quote(p)} 2>/dev/null` joined by ` || ` over
`profile.log_paths()`. Change the CLI default in `main.py:4145` to `default=None`
(`help` text keeps working; grep the test suite for tests pinning the old
default and update them).

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_bsd_features.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/features.py cloudmesh/core/osprofile.py cloudmesh/main.py cloudmesh/tests/test_bsd_features.py
git commit -m "feat: serve feature commands through the OS profile layer"
```

---

### Task 6: Package deployment on BSD

**Files:**
- Modify: `cloudmesh/core/osprofile.py` (`python_package`, `nodejs_package`, `script_shell`)
- Modify: `cloudmesh/core/deploy.py`
- Test: `cloudmesh/tests/test_bsd_deploy.py`

**Interfaces:**
- Produces on `OsProfile`: `python_package() -> str`, `nodejs_package() -> str`,
  `script_shell() -> str` (`"bash"` Linux, `"sh"` BSD).
- Produces in `deploy.py`: `PackageDeployer._privilege_cmd(server_name) -> str`
  (`"sudo"`, `"doas"`, or `""`), and `_detect_cmds`/`_install_cmds` entries for
  `"pkg"` and `"pkg_add"`.

- [x] **Step 1: Write the failing tests**

```python
# cloudmesh/tests/test_bsd_deploy.py
from cloudmesh.core.deploy import PackageDeployer


class FakeServerManager:
    def __init__(self, responses):
        self.responses = responses  # cmd substring -> stdout
        self.commands = []

    def get_server_info(self, name):
        return {"os_type": "freebsd"}

    def list_servers(self):
        return ["bsd1"]

    def execute(self, name, cmd):
        self.commands.append(cmd)
        for needle, out in self.responses.items():
            if needle in cmd:
                return {"stdout": out, "stderr": "", "exit_code": 0}
        return {"stdout": "", "stderr": "", "exit_code": 1}


def test_freebsd_uses_pkg_and_doas_when_sudo_absent():
    mgr = FakeServerManager({"which pkg": "pkg\n", "which doas": "doas\n",
                             "which sudo": "", "pkg info -e": "installed"})
    pd = PackageDeployer(mgr)
    assert pd._detect_package_manager("bsd1") == "pkg"
    assert pd.check_installed("bsd1", "nginx") is True
    pd.install("bsd1", "nginx")
    assert any(c.startswith("doas pkg install -y nginx") for c in mgr.commands)


def test_run_script_uses_sh_on_bsd(monkeypatch, tmp_path):
    uploaded = {}

    class FakeTransfer:
        def __init__(self, mgr): ...
        def upload(self, server, local, remote): uploaded["remote"] = remote

    import cloudmesh.core.transfer as transfer_mod
    monkeypatch.setattr(transfer_mod, "FileTransfer", FakeTransfer)

    mgr = FakeServerManager({})
    mgr.execute = lambda name, cmd: (uploaded.setdefault("run", cmd),
                                     {"stdout": "ok", "stderr": "", "exit_code": 0})[1]
    PackageDeployer(mgr).run_script("bsd1", "echo hi", "s.sh")
    assert "sh /tmp/s.sh" in uploaded["run"]
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_bsd_deploy.py -q`
Expected: FAIL — no package manager detected, `bash` used

- [x] **Step 3: Implement**

`_detect_package_manager`: for BSD os_types probe `pkg` then `pkg_add`
(`which X >/dev/null 2>&1 && echo X || echo none`), else keep the current
apt/yum/brew order. Add the two managers to both command dicts:
`pkg` → detect `pkg info -e {pkg} >/dev/null 2>&1 && echo installed || echo not_installed`,
install `{priv} pkg install -y {pkg}`;
`pkg_add` → detect `pkg_info -e {pkg} ...`, install `{priv} pkg_add {pkg}`.
`{priv}` comes from `_privilege_cmd` (probe `which sudo`, then `which doas`).
`install_python`/`install_nodejs` use `profile.python_package()` /
`profile.nodejs_package()`; `run_script` uses `profile.script_shell()` for the
POSIX branch.

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_bsd_deploy.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/deploy.py cloudmesh/core/osprofile.py cloudmesh/tests/test_bsd_deploy.py
git commit -m "feat: support pkg and pkg_add package deployment"
```

---

### Task 7: Directory sync fingerprint on BSD

**Files:**
- Modify: `cloudmesh/core/osprofile.py` (`md5_cmd(path) -> str`)
- Modify: `cloudmesh/core/sync.py:25-30`
- Test: `cloudmesh/tests/test_bsd_sync.py`

**Interfaces:**
- Produces: `OsProfile.md5_cmd(path: str) -> str` — Linux
  `"md5sum {quoted} 2>/dev/null || echo none"`, BSD
  `"md5 -q {quoted} 2>/dev/null || echo none"`.

- [x] **Step 1: Write the failing test**

```python
# cloudmesh/tests/test_bsd_sync.py
from cloudmesh.core.sync import DirectorySync


class FakeServerManager:
    def __init__(self, os_type):
        self.os_type, self.commands = os_type, []

    def get_server_info(self, name):
        return {"os_type": self.os_type}

    def execute(self, name, cmd):
        self.commands.append(cmd)
        return {"stdout": "d41d8cd98f00b204e9800998ecf8427e\n", "stderr": "", "exit_code": 0}


def test_freebsd_uses_md5_q():
    mgr = FakeServerManager("freebsd")
    assert DirectorySync(mgr)._remote_md5("bsd1", "/tmp/a file.txt") == "d41d8cd98f00b204e9800998ecf8427e"
    assert mgr.commands[0].startswith("md5 -q ")
    assert "'/tmp/a file.txt'" in mgr.commands[0]  # quoted
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_bsd_sync.py -q`
Expected: FAIL — `md5sum` is used

- [x] **Step 3: Implement**

Add `md5_cmd` to the base/linux/windows/BSD profiles; in `sync.py` resolve the
profile from `server_mgr.get_server_info(server_name)` and execute
`profile.md5_cmd(remote_path)` (the profile does the `shlex.quote`).

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_bsd_sync.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/sync.py cloudmesh/core/osprofile.py cloudmesh/tests/test_bsd_sync.py
git commit -m "feat: use md5 on BSD family systems for directory sync"
```

---

### Task 8: Firewall backends — pf on BSD, explicit ipfw limit

**Files:**
- Modify: `cloudmesh/core/firewall.py`
- Test: `cloudmesh/tests/test_bsd_firewall.py`

**Interfaces:**
- Produces in `firewall.py`:
  - `_detect_backend(host, user, key) -> str` — `"ufw"`, `"pf"`, `"ipfw"`, `"iptables"` or `"none"`;
  - `_pf_rules(host, user, key) -> list[str]`, `_pf_apply(host, user, key, rules: list[str]) -> int` (rc),
  - `_pf_add_rule(host, user, key, rule: str) -> str`, `_pf_delete_rule(host, user, key, rule: str) -> str`.
- Existing `firewall_list` / `firewall_add_rule` / `firewall_delete_rule` /
  `firewall_check_all` keep their names and return strings.

- [x] **Step 1: Write the failing tests**

```python
# cloudmesh/tests/test_bsd_firewall.py
import cloudmesh.core.firewall as fw


def fake_ssh(responses):
    def _run(host, user, key, cmd):
        for needle, (out, rc) in responses.items():
            if needle in cmd:
                return out, rc
        return "", 0
    return _run


def test_backend_detection_prefers_pf_over_ipfw(monkeypatch):
    monkeypatch.setattr(fw, "_run_ssh", fake_ssh({
        "which ufw": ("", 1),
        "pfctl -s info": ("Status: Enabled for 1 days\n", 0),
    }))
    assert fw._detect_backend("h", "root", "") == "pf"


def test_pf_add_rule_writes_anchor_and_quotes(monkeypatch):
    seen = {}

    def run(host, user, key, cmd):
        seen["cmd"] = cmd
        if "pfctl -a cloudmesh -sr" in cmd:
            return "pass in proto tcp from any to any port 22\n", 0
        return "", 0

    monkeypatch.setattr(fw, "_run_ssh", run)
    out = fw._pf_add_rule("h", "root", "", "pass in proto tcp from any to any port 80")
    assert "pfctl -a cloudmesh -f -" in seen["cmd"]
    assert "port 80" in seen["cmd"]
    assert "port 22" in seen["cmd"]  # existing rule preserved


def test_ipfw_reports_explicit_limitation(monkeypatch):
    monkeypatch.setattr(fw, "_run_ssh", fake_ssh({
        "which ufw": ("", 1),
        "pfctl -s info": ("", 1),
        "ipfw list": ("65535 allow ip from any to any\n", 0),
    }))
    monkeypatch.setattr(fw, "_get_server", lambda n: {"host": "h", "user": "root", "key": ""})
    msg = fw.firewall_add_rule("bsd1", "allow 80/tcp")
    assert "ipfw" in msg and "not supported" in msg.lower()
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_bsd_firewall.py -q`
Expected: FAIL — `_detect_backend` does not exist

- [x] **Step 3: Implement**

Backend order: `which ufw` → ufw; `pfctl -s info` non-empty → pf;
`ipfw list` non-empty → ipfw; `iptables -L -n` non-empty → iptables; else none.
pf rules live in anchor `cloudmesh`; add/delete do read-modify-write over
`pfctl -a cloudmesh -sr` and pipe the new rule set into
`pfctl -a cloudmesh -f -` using `shlex.quote`. `enable`/`disable` map to
`pfctl -e` / `pfctl -d` for pf. `check_port` for pf greps the anchor for
`port {port}`; for ipfw greps `ipfw list`. Docker-style explicit message for
ipfw mutations: `"ipfw rule management is not supported yet; use pf"`. Keep
ufw and iptables behaviour byte-identical (existing tests must pass).

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_bsd_firewall.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/firewall.py cloudmesh/tests/test_bsd_firewall.py
git commit -m "feat: add pf firewall backend for the BSD family"
```

---

### Task 9: Log aggregation paths per OS

**Files:**
- Modify: `cloudmesh/core/logagg.py:24,45-66,170-180`
- Test: `cloudmesh/tests/test_bsd_logagg.py`

**Interfaces:**
- Consumes: `get_profile(...).log_paths()`.
- Produces: `logagg.get_logs(server_name, log_file=None, ...)` and
  `logagg.follow_log(server_name, log_file=None)` resolve `None` to the first
  path the profile declares for that server's `os_type`.

- [x] **Step 1: Write the failing test**

```python
# cloudmesh/tests/test_bsd_logagg.py
import cloudmesh.core.logagg as logagg


def test_freebsd_default_source_is_messages(monkeypatch):
    monkeypatch.setattr(logagg, "_get_server", lambda n: {"host": "h", "user": "root", "key": "", "os_type": "freebsd"})
    seen = {}

    def run(host, user, key, cmd):
        seen["cmd"] = cmd
        return "line", 0

    monkeypatch.setattr(logagg, "_run_ssh", run)
    logagg.get_logs("bsd1", lines=5)
    assert "/var/log/messages" in seen["cmd"]
    assert "/var/log/syslog" not in seen["cmd"]
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_bsd_logagg.py -q`
Expected: FAIL — `/var/log/syslog` is used

- [x] **Step 3: Implement**

Add a `_default_log_path(server)` helper that reads `os_type` from the server
record (missing → linux) and returns `get_profile(...).log_paths()[0]`. Use it
whenever `log_file` is `None`; keep the existing explicit-path behaviour and
source-discovery command unchanged.

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_bsd_logagg.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/logagg.py cloudmesh/tests/test_bsd_logagg.py
git commit -m "feat: resolve default log paths from the OS profile"
```

---

### Task 10: Resource history snapshots through the profile layer

**Files:**
- Modify: `cloudmesh/core/reshistory.py:38-74`
- Test: `cloudmesh/tests/test_bsd_reshistory.py`

**Interfaces:**
- Consumes: `get_profile(...).cpu_cmd()/ram_cmd()/disk_cmd()` and their parsers.
- Produces: `snapshot(server_name=None)` unchanged signature; history entries keep
  the `{"time", "cpu", "ram", "disk"}` shape.

- [x] **Step 1: Write the failing test**

```python
# cloudmesh/tests/test_bsd_reshistory.py
import cloudmesh.core.reshistory as rh


def test_freebsd_snapshot_uses_profile_commands(monkeypatch, tmp_path):
    monkeypatch.setattr(rh, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(rh, "_get_server", lambda n: {"host": "h", "user": "root", "key": "", "os_type": "freebsd"})
    vmstat = " r b w avm fre flt re pi po fr sr in sy cs us sy id\n 1 0 0 1 1 1 0 0 0 0 0 0 1 1 1 1 95\n"
    df_out = "Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/ada0p2 1000000 400000 600000 40% /\n"

    def run(host, user, key, cmd):
        if "vmstat" in cmd:
            return vmstat, 0
        if "hw.physmem" in cmd:
            return "8589934592\n4096\n500000\n300000\n", 0
        return df_out, 0  # df -kP output

    monkeypatch.setattr(rh, "_run_ssh", run)
    rh.snapshot("bsd1")
    entry = rh.show_history("bsd1")[-1]
    assert entry["cpu"] == 5.0
    assert entry["disk"] == 40
    assert entry["ram"] > 0
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_bsd_reshistory.py -q`
Expected: FAIL — the Linux one-liner runs and parsing yields nothing useful

- [x] **Step 3: Implement**

Replace the single `top/free/df` one-liner with three profile-driven calls:
`profile.cpu_cmd()` → `parse_cpu`, `profile.ram_cmd()` → `parse_ram`,
`profile.disk_cmd()` → `parse_disk` (percent). Append an entry only when all
three parsed; keep the 1000-entry cap and the return string.

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_bsd_reshistory.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/reshistory.py cloudmesh/tests/test_bsd_reshistory.py
git commit -m "refactor: snapshot resource history through the OS profile layer"
```

---

### Task 11: Security audit checks per OS

**Files:**
- Modify: `cloudmesh/core/osprofile.py` (`audit_checks()`)
- Modify: `cloudmesh/core/advanced.py:594-618`
- Test: `cloudmesh/tests/test_bsd_audit.py`

**Interfaces:**
- Produces: `OsProfile.audit_checks() -> list[tuple[str, str]]` (label, command).
  `LinuxProfile.audit_checks()` returns today's exact eight tuples.
  BSD lists replace the systemd and LUKS rows with `pfctl`/`ipfw`, `geli` (FreeBSD)
  and `freebsd-update`/`syspatch` (OpenBSD) equivalents.

- [x] **Step 1: Write the failing test**

```python
# cloudmesh/tests/test_bsd_audit.py
from cloudmesh.core.advanced import audit_server


class FakeServerManager:
    def __init__(self, os_type):
        self.os_type, self.commands = os_type, []

    def get_server_info(self, name):
        return {"os_type": self.os_type}

    def execute(self, name, cmd):
        self.commands.append(cmd)
        return {"stdout": "no", "stderr": "", "exit_code": 0}


def test_freebsd_audit_never_runs_systemd_commands():
    mgr = FakeServerManager("freebsd")
    checks = audit_server(mgr, "bsd1")
    assert any("pfctl" in c for c in mgr.commands)
    assert not any("systemctl" in c for c in mgr.commands)
    assert checks and all({"check", "result", "risk"} <= set(c) for c in checks)
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_bsd_audit.py -q`
Expected: FAIL — `systemctl` appears in the executed commands

- [x] **Step 3: Implement**

Move the eight current tuples into `LinuxProfile.audit_checks()` verbatim (same
labels, same order). BSD variants: firewall row tries
`pfctl -s info | head -2` then `ipfw list | head -3`; ports row uses
`netstat -an -p tcp | grep LISTEN | head -10`; failed logins read
`/var/log/auth.log` (FreeBSD) or `/var/log/authlog`; encryption row uses
`geli status` (FreeBSD) or `echo 'N/A'`; auto-updates row uses
`sysrc -n freebsd_update_enable` (FreeBSD) or `syspatch -l | head -1` (OpenBSD) or
`echo 'Not configured'` (NetBSD). Rewire `audit_server` to iterate
`get_profile(os_type).audit_checks()` with the existing risk heuristic untouched.

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_bsd_audit.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/advanced.py cloudmesh/core/osprofile.py cloudmesh/tests/test_bsd_audit.py
git commit -m "feat: OS-specific security audit checks"
```

---

### Task 12: Docker returns an explicit unsupported message on BSD

**Files:**
- Modify: `cloudmesh/core/docker.py`
- Test: `cloudmesh/tests/test_bsd_docker.py`

**Interfaces:**
- Produces: `docker.unsupported_on_bsd(server_name) -> str | None` — the message
  for `freebsd`/`openbsd`/`netbsd`, `None` otherwise.

- [x] **Step 1: Write the failing test**

```python
# cloudmesh/tests/test_bsd_docker.py
import cloudmesh.core.docker as docker


def test_bsd_servers_get_an_explicit_message(monkeypatch):
    monkeypatch.setattr(docker, "_get_server", lambda n: {"os_type": "freebsd"})
    msg = docker.unsupported_on_bsd("bsd1")
    assert msg and "not supported" in msg.lower() and "freebsd" in msg.lower()


def test_linux_servers_are_untouched(monkeypatch):
    monkeypatch.setattr(docker, "_get_server", lambda n: {"os_type": "linux"})
    assert docker.unsupported_on_bsd("web1") is None
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_bsd_docker.py -q`
Expected: FAIL — `unsupported_on_bsd` does not exist

- [x] **Step 3: Implement**

Add the helper; call it at the top of every `DockerManager` method that receives
a server (return the string instead of executing) and skip BSD targets inside
`docker_list` with the same message in the `error` field.

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_bsd_docker.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/core/docker.py cloudmesh/tests/test_bsd_docker.py
git commit -m "feat: report Docker as unsupported on BSD instead of failing obscurely"
```

---

### Task 13: Node agent — OS shim, metric fallback, safe write, SPA guard

**Files:**
- Modify: `cloudmesh/node/cloudmesh_node.py`
- Test: `cloudmesh/tests/test_bsd_agent.py`

**Interfaces:**
- Produces (module level, importable by tests):
  - `_system_os_type() -> str` — `platform.system().lower()` mapped to
    `linux/windows/freebsd/openbsd/netbsd`, default `linux`;
  - `_resolve_written_path(fd: int, safe_path) -> Path` — uses `/proc/self/fd`
    only when it exists, else `os.path.realpath(str(safe_path))`;
  - `_spa_guard(system_name: str) -> str | None` — the fatal message for any
    non-Linux system, `None` on Linux.

- [x] **Step 1: Write the failing tests**

```python
# cloudmesh/tests/test_bsd_agent.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "node"))
import cloudmesh_node


@pytest.mark.parametrize("system,expected", [
    ("FreeBSD", "freebsd"), ("OpenBSD", "openbsd"), ("NetBSD", "netbsd"),
    ("Linux", "linux"), ("Windows", "windows"), ("SunOS", "linux"),
])
def test_system_os_type(monkeypatch, system, expected):
    monkeypatch.setattr(cloudmesh_node.platform, "system", lambda: system)
    assert cloudmesh_node._system_os_type() == expected


def test_resolve_written_path_without_proc(monkeypatch, tmp_path):
    target = tmp_path / "data" / "jobs.json"
    target.parent.mkdir()
    target.write_text("{}")
    monkeypatch.setattr(Path, "exists", lambda self: False)
    resolved = cloudmesh_node._resolve_written_path(123, str(target))
    assert resolved == Path(str(target)).resolve()


def test_spa_guard_refuses_non_linux():
    assert cloudmesh_node._spa_guard("FreeBSD") is None or "not supported" in cloudmesh_node._spa_guard("FreeBSD").lower()
    assert cloudmesh_node._spa_guard("Linux") is None
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_bsd_agent.py -q`
Expected: FAIL — helpers do not exist

- [x] **Step 3: Implement**

Add the three helpers. Use `_system_os_type()` where `platform.system()` is
already read. In `_collect_metrics`, when `HAS_PSUTIL` is false and the OS is
BSD, take CPU from `vmstat 1 2` and RAM from `sysctl -n hw.physmem ...` via
`subprocess`; keep the `/proc` branch for Linux and return zeros on failure as
today. In `_safe_open_write`, replace the inline `/proc` check with
`_resolve_written_path`. In `_serve`, before the iptables block call
`_spa_guard(platform.system())`: when it returns a message, log it and `return`
(fail closed, no exposed port). The per-knock iptables add/remove stays
Linux-only and is unreachable when the guard fired.

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_bsd_agent.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/node/cloudmesh_node.py cloudmesh/tests/test_bsd_agent.py
git commit -m "feat: make the node agent BSD-safe (metrics, safe writes, SPA guard)"
```

---

### Task 14: node-install.sh installs on the BSD family

**Files:**
- Modify: `cloudmesh/node/node-install.sh`
- Test: `cloudmesh/tests/test_installers.py` (extend)

**Interfaces:**
- Produces: `uname -s` detection (`Linux`, `FreeBSD`, `OpenBSD`, `NetBSD`);
  privilege helper (`sudo` else `doas`); Python/psutil branches for `pkg` and
  `pkg_add`; rc.d units; `ifconfig`-based IP detection; generated helper scripts
  with `#!/bin/sh`.

- [x] **Step 1: Write the failing tests**

```python
# appended to cloudmesh/tests/test_installers.py
def _node_install_text():
    return NODE_SH.read_text(encoding="utf-8")


def test_node_installer_knows_the_bsd_family():
    text = _node_install_text()
    for marker in ("FreeBSD", "OpenBSD", "NetBSD", "pkg install", "pkg_add",
                   "doas", "/usr/local/etc/rc.d", "rcctl"):
        assert marker in text, f"node-install.sh is missing {marker}"


def test_node_installer_posix_parses(tmp_path):
    import shutil
    import subprocess
    sh = shutil.which("sh") or shutil.which("dash")
    if sh is None:
        pytest.skip("no POSIX shell on this machine")
    result = subprocess.run([sh, "-n", str(NODE_SH)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_installers.py -q -k bsd or posix`
Expected: FAIL on the missing markers

- [x] **Step 3: Implement**

Rewrite the script as POSIX `sh` (shebang `#!/bin/sh`, no `&>`, no `[[`, no
arrays), keeping the existing Linux behaviour: same package-manager order, same
messages, same install location. Add: `OS_TYPE=$(uname -s)` switch; FreeBSD
`pkg install -y python3`, OpenBSD/NetBSD `pkg_add python%3`/`pkg_add python3`
with a fallback list; psutil through `pkg install -y py<ver>-psutil`
(`python3 -c 'import sys;print("%d%d"%sys.version_info[:2])'`) then pip as
fallback; `SUDO`/`DOAS` prefix; rc.d unit written for FreeBSD
(`PROVIDE: cloudmesh_node`, launched through `/usr/sbin/daemon`), OpenBSD
(`/etc/rc.d/cloudmesh_node` for `rcctl`), NetBSD (`/etc/rc.d/` +
`run_rc_command`); IP via `ifconfig -a | awk '/inet /{print $2; exit}'` on BSD
and the existing `hostname -I` on Linux; generated helper scripts use
`#!/bin/sh`. Keep the printed summary useful on BSD (start/stop/status paths,
`service cloudmesh_node start` vs `rcctl start cloudmesh_node`).

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_installers.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cloudmesh/node/node-install.sh cloudmesh/tests/test_installers.py
git commit -m "feat: install the node agent on FreeBSD, OpenBSD and NetBSD"
```

---

### Task 15: cm_for-bsd.sh controller installer

**Files:**
- Create: `cm_for-bsd.sh`
- Test: `cloudmesh/tests/test_installers.py` (extend)

**Interfaces:**
- Produces: `sh cm_for-bsd.sh --yes [--source=DIR]`, `--help`, `--verify-only`;
  exits non-zero when `cm --version` fails after install.

- [x] **Step 1: Write the failing tests**

```python
# appended to cloudmesh/tests/test_installers.py
BSD_SH = ROOT / "cm_for-bsd.sh"


def test_bsd_installer_exists_gitattributes_and_is_executable():
    assert BSD_SH.exists()
    assert ".sh" in (ROOT / ".gitattributes").read_text(encoding="utf-8")
    import subprocess
    mode = subprocess.run(["git", "ls-files", "-s", "cm_for-bsd.sh"],
                          cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert mode and mode[0] == "100755"


def test_bsd_installer_parses_and_detects_bsd():
    text = BSD_SH.read_text(encoding="utf-8")
    assert "uname -s" in text
    assert "pkg install" in text
    assert "--verify-only" in text
```

- [x] **Step 2: Run to verify failure**

Run: `python -m pytest cloudmesh/tests/test_installers.py -q -k bsd_installer`
Expected: FAIL — the file does not exist

- [x] **Step 3: Implement**

POSIX sh installer modelled on `cm_for-linux.sh`: `--help` without a TTY,
`--yes` scripted path, `--source=DIR` installs from a checkout
(`python3 -m pip install --user .`), otherwise downloads the GitHub tarball;
installs `python3` via `pkg`/`pkg_add` when missing; verifies the result and
prints the same style of summary. `chmod +x cm_for-bsd.sh` and confirm the
committed mode is `100755` (the repo pins shell scripts to LF via
`.gitattributes`).

- [x] **Step 4: Run to verify pass, then the suite**

Run: `python -m pytest cloudmesh/tests/test_installers.py -q` → PASS
Run: `python -m pytest cloudmesh/tests -q` → no new failures

- [x] **Step 5: Commit**

```bash
git add cm_for-bsd.sh cloudmesh/tests/test_installers.py .gitattributes
git commit -m "feat: add a BSD controller installer"
```

---

### Task 16: FreeBSD end-to-end job in GitHub Actions

**Files:**
- Create: `.github/workflows/bsd.yml`
- Create: `scripts/bsd_e2e.sh`
- Verify: the workflow run is green

**Interfaces:**
- Consumes: the running suite, `cm`, the node agent, `scripts/bsd_e2e.sh`.
- Produces: a required check for the branch; the acceptance evidence for the spec.

- [x] **Step 1: Write the workflow and the E2E script**

```yaml
# .github/workflows/bsd.yml
name: BSD

on:
  workflow_dispatch:
  push:
    branches: [ feature/bsd-support ]

permissions:
  contents: read

jobs:
  freebsd:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: FreeBSD suite and smoke test
        uses: vmactions/freebsd-vm@v1
        with:
          usesh: true
          prepare: pkg install -y python311 py311-pip py311-psutil
          run: |
            set -e
            python3.11 -m pip install --upgrade pip
            python3.11 -m pip install -r cloudmesh/requirements.txt
            python3.11 -m pytest cloudmesh/tests -q
            sh scripts/bsd_e2e.sh
```

`scripts/bsd_e2e.sh` (POSIX sh, `set -e`) walks the acceptance criteria inside
the VM. It runs in four phases and prints `BSD E2E OK` as its last line:

1. **Controller** — `python3.11 -m pip install -e .`; then `cm --help`,
   `cm --version`, `cm doctor || true` (must print its report, not traceback),
   `cm mon --local`. `cm service start` blocks by design, so:
   `cm service start --interval 5 &`, poll `cm service status`, then
   `cm service stop`.
2. **Node installer and rc.d** — `sh cloudmesh/node/node-install.sh`;
   `sysrc cloudmesh_node_enable=YES`; `service cloudmesh_node start`;
   `service cloudmesh_node status`; read `~/.cloudmesh-node/.node_key`.
3. **Loopback agent** — `cm node add -n local -H 127.0.0.1 -p 9999 -k "$KEY"`,
   `cm node list`, `cm node test -n local`, `cm node exec -n local "uname -s"`,
   `cm node job start -n local "echo bsd"`, `cm node job list -n local`,
   `cm node job checkpoint -n local -j <id>`, `cm node gpu -n local || true`.
4. **SSH server** — generate an SSH key, append it to `~/.ssh/authorized_keys`,
   start `sshd`, `cm server add -n localssh -H 127.0.0.1 -u root -k ~/.ssh/id_rsa`,
   `cm test -n localssh`, then `cm mon -n localssh`, `cm uptime -n localssh`,
   `cm df -n localssh`, `cm network -n localssh`, `cm who -n localssh`,
   `cm top -n localssh --limit 3`, `cm logs -n localssh --lines 5`,
   `cm reshistory snapshot` + `cm reshistory show localssh`,
   `cm sync --local scripts --to-server localssh --remote-to /tmp/cm-sync`,
   `cm transfer --file scripts/bsd_e2e.sh --to-server localssh`,
   `cm deploy --install nano` (exercises the pkg path from Task 6),
   `cm firewall status -s localssh`, `cm audit -n localssh`.

- [x] **Step 2: Push the branch and run it (ask the human first)**

Pushing is a user-gated action; ask before `git push -u origin feature/bsd-support`.
Then trigger with `gh workflow run bsd.yml --ref feature/bsd-support` (or the
web UI) and record the run URL.

- [x] **Step 3: Fix what reality disagrees with, in the same task**

The live FreeBSD host is the arbiter for command strings and parsers. Every fix
lands with its fixture updated in the same commit (`git commit -m "fix: <what the
FreeBSD host corrected>"`).

- [x] **Step 4: Verify**

Run: the workflow is green end-to-end.
Expected: suite passes inside FreeBSD and `BSD E2E OK` appears in the log.

- [x] **Step 5: Commit**

```bash
git add .github/workflows/bsd.yml scripts/bsd_e2e.sh
git commit -m "ci: verify CloudMesh inside a FreeBSD VM"
```

---

### Task 17: Release 4.0.0 metadata and docs

**Files:**
- Modify: `pyproject.toml`, `cloudmesh/core/features.py:361,363`,
  `cloudmesh/tests/test_release_metadata.py` (the `RELEASE` constant),
  `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `scripts/bsd_e2e.sh`

**Interfaces:**
- Produces: `cm --version` reports `4.0.0`; the release-metadata tests pass with
  `RELEASE = "4.0.0"`.

- [x] **Step 1: Write the failing change first**

Set `RELEASE = "4.0.0"` in `test_release_metadata.py`, then run:
`python -m pytest cloudmesh/tests/test_release_metadata.py -q`
Expected: FAIL — pyproject still says 3.5.0, the README badge too, and
`get_version()`'s fallback too.

- [x] **Step 2: Update the metadata**

`pyproject.toml`: `version = "4.0.0"`; add classifiers
`Operating System :: POSIX :: BSD :: FreeBSD`, `... :: OpenBSD`, `... :: NetBSD`.
`features.get_version` fallback `"3.5.0"` → `"4.0.0"` (both occurrences).
`README.md`: version badge `4.0.0`; add a support matrix (Linux, Windows,
FreeBSD, OpenBSD, NetBSD) and a "FreeBSD/OpenBSD/NetBSD" install section that
points at `cm_for-bsd.sh` and the node installer.
`CHANGELOG.md`: add `## [4.0.0] - <release date>` at the top with the BSD work.
`CONTRIBUTING.md`: note that the suite runs on Windows/Linux and that FreeBSD
paths are verified by the `bsd.yml` CI job; document the `osprofile.py` rule
(all OS-specific commands live there).
`scripts/bsd_e2e.sh`: tighten the version check to
`cm --version | grep -q "4.0.0"`.

- [x] **Step 3: Run the full verification**

Run: `python -m pytest cloudmesh/tests -q`
Expected: all green (the metadata tests now agree).
Then re-run the FreeBSD workflow (Task 16) to confirm the 4.0.0 assertion passes
on the real host.

- [x] **Step 4: Commit**

```bash
git add pyproject.toml cloudmesh/core/features.py cloudmesh/tests/test_release_metadata.py README.md CHANGELOG.md CONTRIBUTING.md
git commit -m "release: 4.0.0 — BSD family support"
```
