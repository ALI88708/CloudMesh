import subprocess
import threading
from types import SimpleNamespace

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
