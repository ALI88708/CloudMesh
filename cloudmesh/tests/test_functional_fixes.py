import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
NODE_DIR = ROOT / "node"
if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))

import cloudmesh_node
from core.node_client import NodeClient
from core.sync import DirectorySync


@pytest.mark.parametrize(
    "source_results",
    [
        [{"success": False, "error": "Could not list remote files"}],
        [{"success": False, "action": "error", "message": "download failed"}],
        [],
    ],
)
def test_sync_between_does_not_sync_failed_or_empty_source(source_results):
    sync = DirectorySync(None)
    sync.sync_from = lambda *_: source_results
    sync.sync_to = lambda *_: pytest.fail("sync_to called for an invalid source")

    result = sync.sync_between("source", "target", "/source", "/target")

    if source_results:
        assert result == source_results
    else:
        assert result == [{"success": False, "error": "No files found to sync from source"}]


def test_sync_between_sends_successfully_downloaded_source_to_target():
    sync = DirectorySync(None)
    sync.sync_from = lambda *_: [{"success": True, "action": "synced", "file": "a.txt"}]
    expected = [{"success": True, "action": "synced"}]
    sync.sync_to = lambda *_: expected

    assert sync.sync_between("source", "target", "/source", "/target") == expected


@pytest.mark.parametrize(
    ("mode", "initial", "content", "expected"),
    [
        ("a", "existing", " data", "existing data"),
        ("ab", b"existing", b" data", b"existing data"),
        ("ab", b"existing", " data", b"existing data"),
        ("w", "existing data", "new", "new"),
        ("wb", b"existing data", b"new", b"new"),
    ],
)
def test_safe_upload_modes_append_or_truncate(
    tmp_path, monkeypatch, mode, initial, content, expected
):
    monkeypatch.setattr(cloudmesh_node, "BASE_DIR", tmp_path)
    path = tmp_path / "data" / "upload.bin"
    path.parent.mkdir()
    path.write_bytes(initial if isinstance(initial, bytes) else initial.encode())

    cloudmesh_node._safe_open_write(path, content, mode)

    assert path.read_bytes() == (
        expected if isinstance(expected, bytes) else expected.encode()
    )


class FragmentedSocket:
    def __init__(self, response):
        self.response = response
        self.closed = False

    def settimeout(self, _timeout):
        pass

    def connect(self, _address):
        pass

    def sendall(self, _data):
        pass

    def recv(self, size):
        if not self.response:
            return b""
        chunk = self.response[: min(size, 1)]
        self.response = self.response[len(chunk):]
        return chunk

    def close(self):
        self.closed = True


def test_node_client_reads_fragmented_response_header(monkeypatch):
    payload = json.dumps({"type": "pong"}).encode()
    response = len(payload).to_bytes(4, "big") + payload
    sock = FragmentedSocket(response)
    monkeypatch.setattr("core.node_client.socket.socket", lambda *_: sock)

    result = NodeClient("localhost")._send({"action": "ping"})

    assert result == {"type": "pong"}
    assert sock.closed


def test_node_client_reports_premature_response_header_close(monkeypatch):
    sock = FragmentedSocket(b"\x00\x00")
    monkeypatch.setattr("core.node_client.socket.socket", lambda *_: sock)

    result = NodeClient("localhost")._send({"action": "ping"})

    assert result == {
        "type": "error",
        "message": "Incomplete response header",
        "request_sent": True,
    }


def test_node_client_marks_connection_failure_as_safe_to_retry(monkeypatch):
    sock = FragmentedSocket(b"")

    def refuse_connection(_address):
        raise ConnectionRefusedError("offline")

    sock.connect = refuse_connection
    monkeypatch.setattr("core.node_client.socket.socket", lambda *_: sock)

    result = NodeClient("localhost")._send({"action": "start_job"})

    assert result["type"] == "error"
    assert result["request_sent"] is False


def test_node_client_marks_incomplete_response_body_as_ambiguous(monkeypatch):
    sock = FragmentedSocket(b"\x00\x00\x00\x05ab")
    monkeypatch.setattr("core.node_client.socket.socket", lambda *_: sock)

    result = NodeClient("localhost")._send({"action": "start_job"})

    assert result == {
        "type": "error",
        "message": "Incomplete response body",
        "request_sent": True,
    }


def test_node_client_can_verify_a_tls_node(monkeypatch):
    payload = json.dumps({"type": "pong"}).encode()
    sock = FragmentedSocket(len(payload).to_bytes(4, "big") + payload)
    monkeypatch.setattr("core.node_client.socket.socket", lambda *_: sock)
    wrapped = []

    class FakeSSLContext:
        def wrap_socket(self, raw_socket, server_hostname):
            wrapped.append((raw_socket, server_hostname))
            return raw_socket

    ca_paths = []
    monkeypatch.setattr(
        "core.node_client.ssl.create_default_context",
        lambda cafile: ca_paths.append(cafile) or FakeSSLContext(),
    )

    client = NodeClient.from_config({
        "host": "node.example",
        "port": 9999,
        "key": "secret",
        "tls": True,
        "ca_file": "private-ca.pem",
    })

    assert client._send({"action": "ping"}) == {"type": "pong"}
    assert wrapped == [(sock, "node.example")]
    assert ca_paths == ["private-ca.pem"]


def test_node_identity_is_created_once_and_persisted(tmp_path, monkeypatch):
    identity_file = tmp_path / ".node_id"
    monkeypatch.setattr(cloudmesh_node, "NODE_ID_FILE", identity_file)

    first = cloudmesh_node.get_node_id()

    assert len(first) == 32
    assert cloudmesh_node.get_node_id() == first
    assert identity_file.read_text(encoding="utf-8") == first


def test_node_agent_marks_running_jobs_unknown_after_restart(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    (jobs_dir / "running-job.json").write_text(
        json.dumps({"id": "running-job", "status": "running"}),
        encoding="utf-8",
    )
    (jobs_dir / "finished-job.json").write_text(
        json.dumps({"id": "finished-job", "status": "completed"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cloudmesh_node, "JOBS_DIR", jobs_dir)
    agent = cloudmesh_node.NodeAgent.__new__(cloudmesh_node.NodeAgent)
    agent._jobs = {}

    agent._load_jobs()

    assert agent._jobs["running-job"]["status"] == "unknown"
    assert "restarted" in agent._jobs["running-job"]["stderr"]
    assert agent._jobs["finished-job"]["status"] == "completed"
    assert json.loads(
        (jobs_dir / "running-job.json").read_text(encoding="utf-8")
    )["status"] == "unknown"


@pytest.mark.parametrize(
    ("tls_cert", "tls_key"),
    [("server.pem", None), (None, "server-key.pem")],
)
def test_node_agent_rejects_partial_tls_configuration(
    tmp_path, monkeypatch, tls_cert, tls_key
):
    monkeypatch.setattr(cloudmesh_node, "JOBS_DIR", tmp_path / "jobs")

    with pytest.raises(ValueError, match="--tls-cert and --tls-key"):
        cloudmesh_node.NodeAgent(tls_cert=tls_cert, tls_key=tls_key)


@pytest.mark.parametrize(
    ("tls_cert", "tls_key"),
    [(None, None), ("server.pem", "server-key.pem")],
)
def test_node_agent_accepts_disabled_or_complete_tls_configuration(
    tmp_path, monkeypatch, tls_cert, tls_key
):
    monkeypatch.setattr(cloudmesh_node, "JOBS_DIR", tmp_path / "jobs")

    agent = cloudmesh_node.NodeAgent(
        auth_key="test-key",
        tls_cert=tls_cert,
        tls_key=tls_key,
    )

    assert agent.tls_cert == tls_cert
    assert agent.tls_key == tls_key


@pytest.mark.parametrize(
    ("arguments", "missing_option"),
    [
        (["start", "--tls-cert", "server.pem"], "--tls-key"),
        (["start", "--tls-key", "server-key.pem"], "--tls-cert"),
    ],
)
def test_node_agent_cli_reports_partial_tls_configuration(
    monkeypatch, capsys, arguments, missing_option
):
    monkeypatch.setattr(sys, "argv", ["cloudmesh_node.py", *arguments])

    with pytest.raises(SystemExit) as exc:
        cloudmesh_node.main()

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert "must be supplied together" in captured.err
    assert missing_option in captured.err


def test_node_agent_logs_and_skips_malformed_persisted_job(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    (jobs_dir / "malformed.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(cloudmesh_node, "JOBS_DIR", jobs_dir)
    messages = []
    monkeypatch.setattr(cloudmesh_node, "_log", messages.append)
    agent = cloudmesh_node.NodeAgent.__new__(cloudmesh_node.NodeAgent)
    agent._jobs = {}

    agent._load_jobs()

    assert agent._jobs == {}
    assert len(messages) == 1
    assert "malformed.json" in messages[0]


def test_node_metrics_are_cached_and_return_independent_snapshots(monkeypatch):
    calls = []
    monkeypatch.setattr(cloudmesh_node, "_METRICS_CACHE", None)
    monkeypatch.setattr(cloudmesh_node, "_METRICS_CACHE_AT", 0.0)
    monkeypatch.setattr(
        cloudmesh_node,
        "_collect_metrics",
        lambda: calls.append(True) or {"ram": {"free_gb": 2}},
    )

    first = cloudmesh_node.get_metrics()
    first["ram"]["free_gb"] = 0
    second = cloudmesh_node.get_metrics()

    assert len(calls) == 1
    assert second["ram"]["free_gb"] == 2


def test_cancelled_job_terminates_process_and_keeps_cancelled_status(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(cloudmesh_node, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(cloudmesh_node, "LOG_FILE", tmp_path / "node.log")
    agent = cloudmesh_node.NodeAgent(port=0, auth_key="test")
    command = f'"{sys.executable}" -c "import time; time.sleep(30)"'

    result = agent._handle_start_job(command, timeout=60)
    job_id = result["job_id"]
    deadline = time.monotonic() + 5
    proc = None
    while time.monotonic() < deadline:
        with agent._lock:
            proc = agent._job_processes.get(job_id)
        if proc is not None:
            break
        time.sleep(0.01)
    assert proc is not None

    assert agent._handle_kill_job(job_id)["success"] is True
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and proc.poll() is None:
        time.sleep(0.01)
    assert proc.poll() is not None

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with agent._lock:
            if job_id not in agent._job_processes:
                break
        time.sleep(0.01)
    with agent._lock:
        assert agent._jobs[job_id]["status"] == "cancelled"
    saved = json.loads((tmp_path / "jobs" / f"{job_id}.json").read_text())
    assert saved["status"] == "cancelled"
