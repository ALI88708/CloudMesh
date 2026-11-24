"""Fleet command execution: honest exit codes, bounded parallelism, timeouts.

`cm run` used to report per-server failures and still exit 0, so any script
wrapping it saw success. It also ran targets one after another, making a fleet
command as slow as the sum of every server's latency. These tests pin the
contract: every failure is visible in the exit code, output can be consumed as
JSON, concurrency is bounded and configurable, and a hung target times out.
"""

import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as cloudmesh_main
from core.scheduler import TaskScheduler


class _CmdLog:
    def __init__(self):
        """Record the commands the CLI reports to the ledger."""
        self.entries = []

    def log(self, *args):
        """Keep one ledger entry per invocation."""
        self.entries.append(args)


class _ServerManager:
    def __init__(self, names, outcomes=None, delay=0.0, barrier=None):
        """Serve canned per-server outcomes and measure concurrency."""
        self.names = list(names)
        self.outcomes = outcomes or {}
        self.delay = delay
        self.barrier = barrier
        self.commands = []
        self.timeouts = []
        self.active = 0
        self.peak = 0
        self._lock = threading.Lock()

    def list_servers(self):
        """Return the configured server names."""
        return list(self.names)

    def execute(self, name, command, timeout=None):
        """Run the canned outcome, tracking how many calls overlap."""
        with self._lock:
            self.commands.append((name, command))
            self.timeouts.append(timeout)
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            if self.barrier is not None:
                self.barrier.wait()
            if self.delay:
                time.sleep(self.delay)
            outcome = self.outcomes.get(
                name, {"exit_code": 0, "stdout": f"ok {name}", "stderr": ""}
            )
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        finally:
            with self._lock:
                self.active -= 1


class _Monitor:
    def __init__(self, samples=None):
        """Return canned metrics, optionally measuring overlap."""
        self.samples = samples or {}
        self.barrier = None
        self.active = 0
        self.peak = 0
        self._lock = threading.Lock()

    def get_all_metrics(self, name):
        """Return the canned sample for `name`."""
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            if self.barrier is not None:
                self.barrier.wait()
            return self.samples[name]
        finally:
            with self._lock:
                self.active -= 1

    def get_best_server(self, names):
        """Pick the first target, matching the real monitor's contract."""
        return (names[0], 10) if names else (None, 0)


class _Groups:
    def __init__(self, devices):
        """Return a fixed member list for every group name."""
        self.devices = devices

    def get_group_devices(self, name):
        """Return the configured members."""
        return list(self.devices)


def _components(server_mgr, scheduler, groups=None, cmd_log=None, monitor=None):
    """Build the 11-tuple every command handler unpacks by position."""
    return (
        None,
        server_mgr,
        monitor,
        scheduler,
        None,
        None,
        None,
        None,
        None,
        groups,
        cmd_log or _CmdLog(),
    )


def _run_args(**overrides):
    """Return the arguments `cmd_run` reads."""
    base = {
        "command": "uptime",
        "best": False,
        "servers": None,
        "max_workers": 10,
        "timeout": None,
        "as_json": False,
        "allow_failures": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _fail(name, code=1, stderr="boom"):
    """Return a failing SSH result."""
    return {"exit_code": code, "stdout": "", "stderr": stderr}


# --- scheduler -------------------------------------------------------------


def test_distribute_command_runs_targets_concurrently():
    """Sequential loops made a fleet command cost the sum of every latency."""
    names = ["a", "b", "c", "d"]
    manager = _ServerManager(
        names, barrier=threading.Barrier(len(names), timeout=5)
    )
    scheduler = TaskScheduler(manager, None)

    results = scheduler.distribute_command("uptime", names, max_workers=4)

    assert all(result["success"] for result in results.values())
    assert manager.peak == 4


def test_distribute_command_respects_max_workers():
    """Unbounded fan-out would open one SSH session per server at once."""
    names = [f"s{i}" for i in range(6)]
    manager = _ServerManager(names, delay=0.05)
    scheduler = TaskScheduler(manager, None)

    scheduler.distribute_command("uptime", names, max_workers=2)

    assert manager.peak <= 2


def test_distribute_command_returns_results_in_target_order():
    """Completion order would shuffle a fleet report from run to run."""
    names = ["a", "b", "c"]
    manager = _ServerManager(names, delay=0.02)
    scheduler = TaskScheduler(manager, None)

    results = scheduler.distribute_command("uptime", names, max_workers=3)

    assert list(results) == names


def test_distribute_command_does_not_run_a_target_twice():
    """A duplicated group member must not receive the command twice."""
    manager = _ServerManager(["a", "b"])
    scheduler = TaskScheduler(manager, None)

    results = scheduler.distribute_command("uptime", ["a", "a", "b"], max_workers=1)

    assert sorted(name for name, _ in manager.commands) == ["a", "b"]
    assert sorted(results) == ["a", "b"]


def test_distribute_command_passes_the_timeout_and_reports_it():
    """A hung target must fail the run, not block it forever."""
    manager = _ServerManager(["a"], outcomes={"a": TimeoutError("timed out")})
    scheduler = TaskScheduler(manager, None)

    results = scheduler.distribute_command("sleep 60", ["a"], timeout=0.5)

    assert manager.timeouts == [0.5]
    assert results["a"]["success"] is False
    assert results["a"]["timed_out"] is True
    assert "timed out" in results["a"]["error"].lower()


def test_distribute_command_keeps_a_nonzero_exit_code_as_failure():
    """A remote command that exits 1 is a failed target."""
    manager = _ServerManager(["a"], outcomes={"a": _fail("a", stderr="no such file")})
    scheduler = TaskScheduler(manager, None)

    result = scheduler.distribute_command("cat missing", ["a"])["a"]

    assert result["success"] is False
    assert result["exit_code"] == 1
    assert result["error"] == "no such file"


# --- cm run ----------------------------------------------------------------


def test_run_exits_nonzero_when_a_server_fails(monkeypatch, capsys):
    """The old handler printed FAIL and returned 0, hiding it from scripts."""
    names = ["web-1", "web-2"]
    manager = _ServerManager(names, outcomes={"web-2": _fail("web-2")})
    scheduler = TaskScheduler(manager, None)
    monkeypatch.setattr(
        cloudmesh_main, "init_components", lambda: _components(manager, scheduler)
    )

    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_run(_run_args(servers="web-1,web-2"))

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "web-2" in out
    assert "boom" in out


def test_run_can_opt_out_of_failure_exit_codes(monkeypatch, capsys):
    """`--allow-failures` is the explicit opt-out, not the default."""
    names = ["web-1", "web-2"]
    manager = _ServerManager(names, outcomes={"web-2": _fail("web-2")})
    scheduler = TaskScheduler(manager, None)
    monkeypatch.setattr(
        cloudmesh_main, "init_components", lambda: _components(manager, scheduler)
    )

    cloudmesh_main.cmd_run(
        _run_args(servers="web-1,web-2", allow_failures=True)
    )

    out = capsys.readouterr().out
    assert "1 of 2" in out


def test_run_json_emits_machine_readable_results(monkeypatch, capsys):
    """Automation needs per-target status without parsing Rich output."""
    names = ["web-1", "web-2"]
    manager = _ServerManager(names, outcomes={"web-2": _fail("web-2")})
    scheduler = TaskScheduler(manager, None)
    monkeypatch.setattr(
        cloudmesh_main, "init_components", lambda: _components(manager, scheduler)
    )

    cloudmesh_main.cmd_run(
        _run_args(servers="web-1,web-2", as_json=True, allow_failures=True)
    )

    raw = capsys.readouterr().out
    payload = json.loads(raw)
    assert payload["web-1"]["success"] is True
    assert payload["web-2"]["success"] is False
    assert payload["web-2"]["exit_code"] == 1
    assert "\u2500" not in raw


def test_run_without_servers_fails_instead_of_reporting_success(monkeypatch, capsys):
    """A fresh install has nothing to run on; that is an error, not a no-op."""
    manager = _ServerManager([])
    scheduler = TaskScheduler(manager, None)
    monkeypatch.setattr(
        cloudmesh_main, "init_components", lambda: _components(manager, scheduler)
    )

    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_run(_run_args())

    assert exc_info.value.code == 1
    assert "No servers configured" in capsys.readouterr().out


def test_run_best_exits_nonzero_when_the_best_server_fails(monkeypatch, capsys):
    """`--best` already failed correctly; keep that contract under the new code."""
    manager = _ServerManager(["web-1"], outcomes={"web-1": _fail("web-1")})
    scheduler = TaskScheduler(manager, _Monitor())
    monkeypatch.setattr(
        cloudmesh_main, "init_components", lambda: _components(manager, scheduler)
    )

    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_run(_run_args(best=True))

    assert exc_info.value.code == 1


def test_run_best_json_is_parseable(monkeypatch, capsys):
    """A human banner line would make the JSON payload unparseable."""
    manager = _ServerManager(["web-1"])
    scheduler = TaskScheduler(manager, _Monitor())
    monkeypatch.setattr(
        cloudmesh_main, "init_components", lambda: _components(manager, scheduler)
    )

    cloudmesh_main.cmd_run(_run_args(best=True, as_json=True))

    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["server"] == "web-1"


def test_run_best_honours_allow_failures(monkeypatch, capsys):
    """The opt-out applies to every target, including the `--best` one."""
    manager = _ServerManager(["web-1"], outcomes={"web-1": _fail("web-1")})
    scheduler = TaskScheduler(manager, _Monitor())
    monkeypatch.setattr(
        cloudmesh_main, "init_components", lambda: _components(manager, scheduler)
    )

    cloudmesh_main.cmd_run(_run_args(best=True, allow_failures=True))

    assert "boom" in capsys.readouterr().out


# --- cm group run ----------------------------------------------------------


def _group_args(**overrides):
    """Return the arguments `cmd_groups` reads in its `run` branch."""
    base = {
        "action": "run",
        "group": "web",
        "command": "uptime",
        "max_workers": 10,
        "timeout": None,
        "as_json": False,
        "allow_failures": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_group_run_exits_nonzero_when_a_member_fails(monkeypatch, capsys):
    """The group path had the same silent-success bug as `cm run`."""
    names = ["web-1", "web-2"]
    manager = _ServerManager(names, outcomes={"web-2": _fail("web-2")})
    scheduler = TaskScheduler(manager, None)
    groups = _Groups(names)
    monkeypatch.setattr(
        cloudmesh_main,
        "init_components",
        lambda: _components(manager, scheduler, groups),
    )

    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_groups(_group_args())

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "web-2" in out


def test_group_run_empty_group_is_an_error(monkeypatch, capsys):
    """An empty group ran nothing and used to return 0."""
    manager = _ServerManager([])
    scheduler = TaskScheduler(manager, None)
    monkeypatch.setattr(
        cloudmesh_main,
        "init_components",
        lambda: _components(manager, scheduler, _Groups([])),
    )

    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_groups(_group_args())

    assert exc_info.value.code == 1
    assert "empty" in capsys.readouterr().out


# --- cm monitor ------------------------------------------------------------


def test_monitor_queries_servers_concurrently(monkeypatch, capsys):
    """Monitoring a fleet should cost the slowest server, not the sum."""
    names = ["web-1", "web-2", "web-3"]
    monitor = _Monitor(
        {name: {"cpu_percent": 1.0, "ram": {}, "disk": {}} for name in names}
    )
    monitor.barrier = threading.Barrier(len(names), timeout=5)
    manager = _ServerManager(names)
    monkeypatch.setattr(
        cloudmesh_main,
        "init_components",
        lambda: _components(
            manager, TaskScheduler(manager, monitor), monitor=monitor
        ),
    )

    cloudmesh_main.cmd_monitor(
        SimpleNamespace(name=None, local=False, as_json=True)
    )

    payload = json.loads(capsys.readouterr().out)
    assert list(payload) == names
    assert monitor.peak == len(names)


# --- parser ----------------------------------------------------------------


def test_the_run_parser_exposes_fleet_controls():
    """The flags have to reach the handler through the real parser."""
    parser = cloudmesh_main.build_parser()

    args = parser.parse_args(
        [
            "run",
            "uptime",
            "--json",
            "--max-workers",
            "3",
            "--timeout",
            "2.5",
            "--allow-failures",
        ]
    )

    assert args.as_json is True
    assert args.max_workers == 3
    assert args.timeout == 2.5
    assert args.allow_failures is True


def test_the_run_parser_defaults_to_bounded_parallelism():
    """Ten workers keeps a large fleet honest without exhausting the laptop."""
    parser = cloudmesh_main.build_parser()

    args = parser.parse_args(["run", "uptime"])

    assert args.max_workers == 10
    assert args.timeout is None
    assert args.allow_failures is False


def test_the_group_run_parser_exposes_fleet_controls():
    """`cm group run` mirrors `cm run`, including the safety flags."""
    parser = cloudmesh_main.build_parser()

    args = parser.parse_args(
        [
            "group",
            "run",
            "-g",
            "web",
            "uptime",
            "--json",
            "--max-workers",
            "2",
            "--timeout",
            "1",
            "--allow-failures",
        ]
    )

    assert args.action == "run"
    assert args.as_json is True
    assert args.max_workers == 2
    assert args.timeout == 1.0
    assert args.allow_failures is True
