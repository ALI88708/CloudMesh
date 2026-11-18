"""Regression tests for the first bug-hunt pass.

Every test pins a defect that shipped in 4.3.0 and stayed green because the
suite never touched these paths: `cm slice` crashed without servers and only
printed its `--execute` commands, the SPA nonce cache evicted recent entries at
random, and the remote benchmark payload could never run -- its failure was
swallowed and the controller's own numbers were shown as the server's.
"""

import hashlib
import hmac
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import main as cloudmesh_main
from core import advanced

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "node"))
import cloudmesh_node  # noqa: E402 - path needs the insert above


class _FakeScheduler:
    def __init__(self, plan):
        """Return a fixed distribution plan and record the call arguments."""
        self.plan = plan
        self.calls = []

    def slice_files(self, files, server_names=None):
        """Record the request and return the canned plan."""
        self.calls.append((files, server_names))
        return self.plan


class _FakeServerManager:
    def __init__(self, results=None):
        """Store canned results keyed by command and record every execution."""
        self.commands = []
        self._results = results or {}

    def execute(self, name, command):
        """Record the call and return its canned or successful result."""
        self.commands.append((name, command))
        return self._results.get(
            command, {"exit_code": 0, "stdout": "ok", "stderr": ""}
        )


def _init_with(monkeypatch, scheduler, server_mgr):
    """Make init_components return the stubs cmd_slice unpacks by position."""
    components = (None, server_mgr, None, scheduler) + (None,) * 7
    monkeypatch.setattr(cloudmesh_main, "init_components", lambda: components)


def _spa_packet(key, nonce, timestamp=None, signature=None):
    """Build the same JSON knock NodeClient.send_spa_knock sends."""
    timestamp = time.time() if timestamp is None else timestamp
    message = f"{timestamp}:{nonce}"
    digest = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return json.dumps(
        {"timestamp": timestamp, "nonce": nonce, "hmac": signature or digest}
    ).encode()


def _listener():
    """Return a SpacListener with a throwaway key and no socket."""
    return cloudmesh_node.SpacListener(
        "test-key", 9998, 9999, 5, lambda *_: None
    )


# --- cm slice -------------------------------------------------------------


def test_slice_without_servers_reports_unassigned_files(monkeypatch, capsys):
    """It indexed the unassigned file list as a plan entry and raised TypeError."""
    scheduler = _FakeScheduler({"unassigned": ["a.txt", "b.txt", "c.txt"]})
    _init_with(monkeypatch, scheduler, _FakeServerManager())
    args = SimpleNamespace(files="a.txt,b.txt,c.txt", servers=None, execute=None)

    cloudmesh_main.cmd_slice(args)

    out = capsys.readouterr().out
    assert "No servers available" in out
    assert "a.txt" in out and "c.txt" in out


def test_slice_execute_runs_the_command_on_the_assigned_server(monkeypatch, capsys):
    """`--execute` printed "Executing..." but never called the server."""
    plan = {
        "web-1": {
            "files": ["a.txt", "b.txt"],
            "count": 2,
            "proportion": 100.0,
            "weight": 10,
        }
    }
    server = _FakeServerManager()
    _init_with(monkeypatch, _FakeScheduler(plan), server)
    args = SimpleNamespace(
        files="a.txt,b.txt", servers="web-1", execute="process {file}"
    )

    cloudmesh_main.cmd_slice(args)

    assert server.commands == [
        ("web-1", "process a.txt"),
        ("web-1", "process b.txt"),
    ]
    assert "OK" in capsys.readouterr().out


def test_slice_execute_exits_nonzero_when_a_command_fails(monkeypatch, capsys):
    """A failed remote command must fail the command, not print a fake success."""
    plan = {
        "web-1": {
            "files": ["a.txt"],
            "count": 1,
            "proportion": 100.0,
            "weight": 10,
        }
    }
    server = _FakeServerManager(
        {"run a.txt": {"exit_code": 7, "stdout": "", "stderr": "boom"}}
    )
    _init_with(monkeypatch, _FakeScheduler(plan), server)
    args = SimpleNamespace(files="a.txt", servers="web-1", execute="run {file}")

    with pytest.raises(SystemExit) as exc:
        cloudmesh_main.cmd_slice(args)

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "boom" in out


# --- SPA nonce cache ------------------------------------------------------


def test_spa_recent_nonce_replay_is_rejected_after_eviction():
    """The set was sliced by list order, so half the recent nonces were dropped."""
    listener = _listener()
    key = "test-key"
    for i in range(10001):
        assert listener._validate_packet(_spa_packet(key, f"n{i}"), "127.0.0.1")

    replayed = [
        nonce
        for nonce in (f"n{i}" for i in range(9000, 9100))
        if listener._validate_packet(_spa_packet(key, nonce), "127.0.0.1")
    ]
    assert replayed == []


def test_spa_invalid_hmac_does_not_enter_the_nonce_cache():
    """Nonces were recorded before HMAC verification, so a flood could evict recent ones."""
    listener = _listener()
    key = "test-key"
    assert listener._validate_packet(_spa_packet(key, "valid"), "127.0.0.1")
    assert not listener._validate_packet(
        _spa_packet(key, "poison", signature="0" * 64), "127.0.0.1"
    )

    assert "poison" not in listener._used_nonces
    assert not listener._validate_packet(_spa_packet(key, "valid"), "127.0.0.1")


# --- benchmark ------------------------------------------------------------


class _LocalPythonServer:
    """Run the command CloudMesh would send over SSH, locally and safely."""

    def execute(self, name, command):
        """Unquote the remote payload and run it with this interpreter."""
        parts = shlex.split(command)
        assert parts[:2] == ["python3", "-c"]
        proc = subprocess.run(
            [sys.executable, "-c", parts[2]],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }


class _FailingServer:
    def execute(self, name, command):
        """Report the missing interpreter a bare node would return."""
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": "python3: command not found",
        }


def test_remote_benchmark_payload_runs_and_returns_real_metrics():
    """The old payload raised TypeError on its first `int += bytes` iteration."""
    result = advanced.run_full_benchmark(_LocalPythonServer(), "web-1")

    assert result["cpu_score"] > 0
    assert result["w"] > 0
    assert result["r"] > 0


def test_remote_benchmark_failure_raises_instead_of_returning_local_numbers():
    """It swallowed every error and returned the controller's own benchmark."""
    with pytest.raises(RuntimeError, match="command not found"):
        advanced.run_full_benchmark(_FailingServer(), "web-1")


def test_cmd_bench_exits_nonzero_when_the_remote_run_fails(monkeypatch, capsys):
    """`cm bench --server` reported local numbers and exit 0 on a failed server."""
    monkeypatch.setattr(
        cloudmesh_main, "init_components", lambda: (None, _FailingServer()) + (None,) * 9
    )
    args = SimpleNamespace(server="web-1")

    with pytest.raises(SystemExit) as exc:
        cloudmesh_main.cmd_bench(args)

    assert exc.value.code == 1
    out = " ".join(capsys.readouterr().out.lower().split())
    assert "failed" in out and "command not found" in out


def test_the_remote_payload_is_throughput_not_a_constant():
    """The old score was 1000000/elapsed, which is ~500000 on every machine."""
    script = advanced.REMOTE_BENCHMARK_SCRIPT

    assert "1000000" not in script
    assert "mkstemp" in script
    assert "'_b'" not in script and '"_b"' not in script


@pytest.mark.skipif(
    os.name == "nt", reason="symlink creation needs privileges on Windows"
)
def test_local_benchmark_does_not_follow_a_predictable_symlink(tmp_path):
    """The fixed temp name let another local user point it at a file to destroy."""
    victim = tmp_path / "victim.db"
    victim.write_bytes(b"important")
    (tmp_path / "_cm_bench_test.tmp").symlink_to(victim)

    advanced.benchmark_disk(path=str(tmp_path), size_mb=1)

    assert victim.read_bytes() == b"important"


def test_cmd_bench_shows_the_remote_cpu_score(monkeypatch, capsys):
    """The remote payload used a key the table never read, so CPU was never shown."""
    monkeypatch.setattr(
        cloudmesh_main,
        "run_full_benchmark",
        lambda mgr=None, name=None: {"cpu_score": 987654, "w": 123.4, "r": 567.8},
    )
    monkeypatch.setattr(
        cloudmesh_main, "init_components", lambda: (None, object()) + (None,) * 9
    )

    cloudmesh_main.cmd_bench(SimpleNamespace(server="web-1"))

    out = capsys.readouterr().out
    assert "CPU Score" in out and "987654" in out
    assert "123.4" in out and "567.8" in out
