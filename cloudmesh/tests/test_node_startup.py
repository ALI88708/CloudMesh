"""Node construction and CLI lifecycle without binding sockets or starting jobs."""

import sys
from unittest.mock import Mock

import pytest

from node import cloudmesh_node as node


@pytest.fixture(autouse=True)
def isolated_node_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(node, "PID_FILE", tmp_path / "node.pid")
    monkeypatch.setattr(node, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(node, "KEY_FILE", tmp_path / ".node_key")
    monkeypatch.setattr(node, "_log", Mock())


@pytest.mark.parametrize("auth_key", [None, "", "explicit-key"])
def test_node_constructor_uses_persisted_key_only_for_empty_auth_key(monkeypatch, auth_key):
    key_lookup = Mock(return_value="persisted-key")
    monkeypatch.setattr(node, "get_or_create_key", key_lookup)
    socket_factory = Mock()
    monkeypatch.setattr(node.socket, "socket", socket_factory)

    agent = node.NodeAgent(
        port=12345, auth_key=auth_key, bind_host="127.0.0.1",
        tls_cert="cert.pem", tls_key="key.pem", spa=True, spa_port=12346, spa_window=17,
    )

    assert agent.auth_key == (auth_key or "persisted-key")
    assert (agent.port, agent.bind_host) == (12345, "127.0.0.1")
    assert (agent.tls_cert, agent.tls_key) == ("cert.pem", "key.pem")
    assert (agent.spa_mode, agent.spa_port, agent.spa_window) == (True, 12346, 17)
    assert node.JOBS_DIR.is_dir()
    assert agent._jobs == {}
    assert agent._running is False
    socket_factory.assert_not_called()
    if auth_key:
        key_lookup.assert_not_called()
    else:
        key_lookup.assert_called_once_with()


def test_node_constructor_propagates_key_io_error(monkeypatch):
    failure = PermissionError("cannot read key")
    monkeypatch.setattr(node, "get_or_create_key", Mock(side_effect=failure))

    with pytest.raises(PermissionError) as exc:
        node.NodeAgent()

    assert exc.value is failure
    assert not node.JOBS_DIR.exists()


def test_node_constructor_propagates_unusable_job_directory():
    node.JOBS_DIR.write_bytes(b"preserve this file")

    with pytest.raises(OSError):
        node.NodeAgent(auth_key="explicit-key")

    assert node.JOBS_DIR.read_bytes() == b"preserve this file"


def test_start_with_live_pid_keeps_pid_and_does_not_construct_agent(monkeypatch, capsys):
    node.PID_FILE.write_text("123", encoding="utf-8")
    alive = Mock(return_value=True)
    monkeypatch.setattr(node, "_is_running", alive)
    constructor = Mock()
    monkeypatch.setattr(node, "NodeAgent", constructor)

    node.cmd_start()

    assert "Already running (PID 123)" in capsys.readouterr().out
    assert node.PID_FILE.read_text(encoding="utf-8") == "123"
    alive.assert_called_once_with(123)
    constructor.assert_not_called()


@pytest.mark.parametrize("recorded_pid", [None, 123], ids=["missing-pid", "stale-pid"])
@pytest.mark.parametrize("interrupted", [False, True], ids=["normal", "keyboard-interrupt"])
def test_start_forwards_settings_and_removes_stale_pid(
    monkeypatch, capsys, recorded_pid, interrupted
):
    if recorded_pid:
        node.PID_FILE.write_text(str(recorded_pid), encoding="utf-8")
    monkeypatch.setattr(node, "_is_running", Mock(return_value=False))
    agent = Mock()
    if interrupted:
        agent.serve.side_effect = KeyboardInterrupt
    constructor = Mock(return_value=agent)
    monkeypatch.setattr(node, "NodeAgent", constructor)
    options = dict(
        port=12345, bind_host="127.0.0.1", tls_cert="cert.pem", tls_key="key.pem",
        spa=True, spa_port=12346, spa_window=17,
    )

    node.cmd_start(**options)

    constructor.assert_called_once_with(**options)
    agent.serve.assert_called_once_with()
    assert not node.PID_FILE.exists()
    assert "127.0.0.1:12345 [SPA(UDP:12346, window:17s)]" in capsys.readouterr().out


@pytest.mark.parametrize("stage", ["construction", "serve"])
def test_start_propagates_startup_errors(monkeypatch, stage):
    failure = RuntimeError("startup failed")
    agent = Mock()
    constructor = Mock(return_value=agent)
    if stage == "construction":
        constructor.side_effect = failure
    else:
        agent.serve.side_effect = failure
    monkeypatch.setattr(node, "NodeAgent", constructor)

    with pytest.raises(RuntimeError) as exc:
        node.cmd_start()

    assert exc.value is failure


@pytest.mark.parametrize("command", ["stop", "status"])
def test_node_cli_dispatches_only_selected_handler(monkeypatch, command):
    handlers = {name: Mock() for name in ["start", "stop", "status"]}
    for name, handler in handlers.items():
        monkeypatch.setattr(node, f"cmd_{name}", handler)
    monkeypatch.setattr(sys, "argv", ["cloudmesh_node.py", command])

    node.main()

    handlers[command].assert_called_once_with()
    for name, handler in handlers.items():
        if name != command:
            handler.assert_not_called()


def test_node_cli_forwards_start_options(monkeypatch):
    start = Mock()
    monkeypatch.setattr(node, "cmd_start", start)
    monkeypatch.setattr(sys, "argv", [
        "cloudmesh_node.py", "start", "--port", "12345", "--bind", "127.0.0.1",
        "--tls-cert", "cert.pem", "--tls-key", "key.pem",
        "--spa", "--spa-port", "12346", "--spa-window", "17",
    ])

    node.main()

    start.assert_called_once_with(
        port=12345, bind_host="127.0.0.1", tls_cert="cert.pem", tls_key="key.pem",
        spa=True, spa_port=12346, spa_window=17,
    )


def test_node_cli_without_command_prints_help_without_dispatch(monkeypatch, capsys):
    handlers = [Mock(), Mock(), Mock()]
    for name, handler in zip(["start", "stop", "status"], handlers):
        monkeypatch.setattr(node, f"cmd_{name}", handler)
    monkeypatch.setattr(sys, "argv", ["cloudmesh_node.py"])

    node.main()

    assert "usage:" in capsys.readouterr().out
    for handler in handlers:
        handler.assert_not_called()


def test_node_cli_does_not_hide_handler_errors(monkeypatch):
    failure = OSError("cannot start")
    monkeypatch.setattr(node, "cmd_start", Mock(side_effect=failure))
    monkeypatch.setattr(sys, "argv", ["cloudmesh_node.py", "start"])

    with pytest.raises(OSError) as exc:
        node.main()

    assert exc.value is failure
