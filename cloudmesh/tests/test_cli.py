import argparse
import json
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


def test_node_add_persists_verified_tls_settings(tmp_path, monkeypatch):
    ca_file = tmp_path / "private-ca.pem"
    ca_file.write_text("test certificate", encoding="utf-8")
    monkeypatch.setattr(
        cloudmesh_main, "NODE_KEYS_FILE", tmp_path / ".node_keys.json"
    )

    cloudmesh_main.cmd_node_add_cloud(
        argparse.Namespace(
            name="secure-node",
            host="node.example",
            port=9999,
            auth_key="secret",
            tls=True,
            ca_file=str(ca_file),
        )
    )

    saved = json.loads(
        (tmp_path / ".node_keys.json").read_text(encoding="utf-8")
    )
    assert saved["secure-node"] == {
        "host": "node.example",
        "port": 9999,
        "key": "secret",
        "tls": True,
        "ca_file": str(ca_file.resolve()),
    }


def test_node_add_requires_tls_when_a_ca_file_is_provided(tmp_path, monkeypatch):
    ca_file = tmp_path / "private-ca.pem"
    ca_file.write_text("test certificate", encoding="utf-8")
    monkeypatch.setattr(
        cloudmesh_main, "NODE_KEYS_FILE", tmp_path / ".node_keys.json"
    )

    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_node_add_cloud(
            argparse.Namespace(
                name="secure-node",
                host="node.example",
                port=9999,
                auth_key="secret",
                tls=False,
                ca_file=str(ca_file),
            )
        )

    assert exc_info.value.code == 2
    assert not (tmp_path / ".node_keys.json").exists()


def test_queue_submit_help_exposes_major_release_options(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["cloudmesh", "queue", "submit", "--help"]
    )

    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.main()

    help_text = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "--min-disk-free" in help_text
    assert "--idempotent" in help_text
    assert "--state-dir" in help_text
