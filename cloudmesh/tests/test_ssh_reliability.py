import subprocess
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.server import ServerManager
from core import ssh_util


class _BufferedStream:
    def __init__(self, channel, data):
        self.channel = channel
        self.data = data
        self.drained = False

    def read(self):
        self.channel.read_barrier.wait(timeout=2)
        self.drained = True
        return self.data


class _BufferedChannel:
    def __init__(self, stdout_data, stderr_data):
        self.read_barrier = threading.Barrier(2)
        self.stdout = _BufferedStream(self, stdout_data)
        self.stderr = _BufferedStream(self, stderr_data)

    def recv_exit_status(self):
        assert self.stdout.drained and self.stderr.drained
        return 17


def test_server_execute_drains_large_stdout_and_stderr_before_exit_status():
    output = b"o" * (3 * 1024 * 1024)
    error = b"e" * (3 * 1024 * 1024)
    channel = _BufferedChannel(output, error)
    streams = SimpleNamespace(channel=channel, read=channel.stdout.read)
    errors = SimpleNamespace(channel=channel, read=channel.stderr.read)
    manager = ServerManager.__new__(ServerManager)
    manager.connect = lambda name: SimpleNamespace(
        exec_command=lambda command: (None, streams, errors)
    )

    result = manager.execute("test", "large-output")

    assert result == {
        "exit_code": 17,
        "stdout": output.decode().strip(),
        "stderr": error.decode().strip(),
    }


@pytest.fixture
def ssh_execution():
    stdout = Mock()
    stdout.read.return_value = b"  output\n"
    stdout.channel.recv_exit_status.return_value = 0
    stderr = Mock()
    stderr.read.return_value = b" warning \n"
    client = Mock()
    client.exec_command.return_value = (None, stdout, stderr)
    manager = ServerManager.__new__(ServerManager)
    manager.connect = Mock(return_value=client)
    return manager, client, stdout, stderr


@pytest.mark.parametrize("exit_code", [0, 23])
@pytest.mark.parametrize(
    ("output", "error"),
    [(b"", b""), (b"  output\r\n", b"\twarning \n"), (" 雪 \n".encode(), " café \n".encode())],
    ids=["empty", "whitespace", "utf8"],
)
def test_server_execute_decodes_both_streams_and_preserves_exit_status(
    ssh_execution, exit_code, output, error
):
    manager, client, stdout, stderr = ssh_execution
    stdout.read.return_value = output
    stderr.read.return_value = error
    stdout.channel.recv_exit_status.return_value = exit_code

    assert manager.execute("target", "printf 'hello'") == {
        "exit_code": exit_code, "stdout": output.decode().strip(), "stderr": error.decode().strip()
    }
    manager.connect.assert_called_once_with("target")
    client.exec_command.assert_called_once_with("printf 'hello'")
    stdout.channel.recv_exit_status.assert_called_once_with()


@pytest.mark.parametrize("stage", ["connect", "execute", "stdout", "stderr"])
def test_server_execute_propagates_connection_and_stream_errors(ssh_execution, stage):
    manager, client, stdout, stderr = ssh_execution
    failing_call = {
        "connect": manager.connect, "execute": client.exec_command,
        "stdout": stdout.read, "stderr": stderr.read,
    }[stage]
    failure = OSError(f"{stage} failed")
    failing_call.side_effect = failure

    with pytest.raises(OSError) as exc:
        manager.execute("target", "uptime")

    assert exc.value is failure
    stdout.channel.recv_exit_status.assert_not_called()


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_server_execute_rejects_invalid_utf8(ssh_execution, stream):
    manager, _, stdout, stderr = ssh_execution
    {"stdout": stdout, "stderr": stderr}[stream].read.return_value = b"\xff"

    with pytest.raises(UnicodeDecodeError):
        manager.execute("target", "uptime")

    stdout.channel.recv_exit_status.assert_not_called()


def test_run_ssh_includes_stderr_for_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        ssh_util.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 23, stdout="partial output\n", stderr="permission denied\n"
        ),
    )

    output, returncode = ssh_util.run_ssh("host", "user", None, "cmd")

    assert returncode == 23
    assert output == "partial output\nstderr: permission denied"


def test_run_ssh_reports_timeout_and_partial_output(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            args[0], kwargs["timeout"], output=b"partial output\n", stderr=b"still running\n"
        )

    monkeypatch.setattr(ssh_util.subprocess, "run", timeout)

    output, returncode = ssh_util.run_ssh("host", "user", None, "cmd", timeout=4)

    assert returncode == 1
    assert output == (
        "partial output\nstderr: still running\nSSH command timed out after 4 seconds"
    )
