import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as cloudmesh_main


def test_test_command_runs_the_suite_with_coverage_when_requested(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cloudmesh_main.subprocess, "run", fake_run)

    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_test(argparse.Namespace(suite=True, coverage=True))

    command, kwargs = calls[0]
    assert exc_info.value.code == 0
    assert command[:4] == [sys.executable, "-m", "pytest", "tests"]
    assert "--cov=core" in command
    assert "--cov=cloudmesh_node" in command
    assert "--cov-fail-under=25" in command
    assert kwargs["cwd"] == ROOT
    assert kwargs["check"] is False


def test_test_command_returns_a_failure_exit_code(monkeypatch):
    monkeypatch.setattr(
        cloudmesh_main.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=3),
    )

    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_test(argparse.Namespace(suite=True, coverage=False))

    assert exc_info.value.code == 3


def test_test_command_keeps_existing_connection_test_behavior(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cloudmesh_main,
        "cmd_server_test",
        lambda args: calls.append(args.name),
    )

    cloudmesh_main.cmd_test(
        argparse.Namespace(name="edge", suite=False, coverage=False)
    )

    assert calls == ["edge"]


def test_coverage_option_requires_suite():
    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_test(
            argparse.Namespace(name="edge", suite=False, coverage=True)
        )

    assert exc_info.value.code == 2


def test_test_command_requires_a_name_for_connection_test():
    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_test(
            argparse.Namespace(name=None, suite=False, coverage=False)
        )

    assert exc_info.value.code == 2
