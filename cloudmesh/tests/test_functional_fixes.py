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

    assert result == {"type": "error", "message": "Incomplete response header"}


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
