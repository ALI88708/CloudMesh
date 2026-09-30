from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

import pytest

from core.task_queue import SmartTaskQueue

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeNodeClient:
    def __init__(self, metrics, start_results=(), check_result=None, kill_result=None):
        self.metrics = metrics
        self.start_results = list(start_results)
        self.check_result = check_result or {"status": "running"}
        self.kill_result = kill_result or {"success": True}
        self.started = []
        self.checked = []
        self.killed = []

    def get_metrics(self):
        return self.metrics

    def start_job(self, command, timeout):
        self.started.append((command, timeout))
        return self.start_results.pop(0)

    def check_job(self, job_id):
        self.checked.append(job_id)
        return self.check_result

    def kill_job(self, job_id):
        self.killed.append(job_id)
        return self.kill_result


def make_queue(tmp_path, clients):
    nodes = {
        name: {"host": name, "port": 9999, "key": name}
        for name in clients
    }
    return SmartTaskQueue(
        nodes,
        queue_dir=tmp_path,
        client_factory=lambda host, _port, _key: clients[host],
    )


def metrics(cpu, ram):
    return {"cpu_percent": cpu, "ram": {"percent": ram}}


def test_submit_selects_node_with_best_cpu_and_memory_resources(tmp_path):
    busy = FakeNodeClient(metrics(80, 85), [{"job_id": "busy-job", "status": "running"}])
    available = FakeNodeClient(
        metrics(15, 25), [{"job_id": "remote-job", "status": "running"}]
    )
    queue = make_queue(tmp_path, {"busy": busy, "available": available})

    job = queue.submit("python work.py", timeout=45)

    assert job["status"] == "running"
    assert job["node"] == "available"
    assert job["node_job_id"] == "remote-job"
    assert available.started == [("python work.py", 45)]
    assert busy.started == []
    saved = json.loads((tmp_path / f"{job['id']}.json").read_text(encoding="utf-8"))
    assert saved["node"] == "available"


def test_submit_retries_only_when_request_was_not_sent(tmp_path):
    unreachable = FakeNodeClient(
        metrics(5, 10),
        [{"type": "error", "message": "Connection refused", "request_sent": False}],
    )
    fallback = FakeNodeClient(
        metrics(20, 20), [{"job_id": "fallback-job", "status": "running"}]
    )
    queue = make_queue(tmp_path, {"unreachable": unreachable, "fallback": fallback})

    job = queue.submit("python work.py")

    assert job["status"] == "running"
    assert job["node"] == "fallback"
    assert [attempt["status"] for attempt in job["attempts"]] == ["not_sent", "accepted"]
    assert fallback.started


def test_submit_does_not_retry_an_ambiguous_request(tmp_path):
    possible_execution = FakeNodeClient(
        metrics(5, 10),
        [{
            "type": "error",
            "message": "Incomplete response header",
            "request_sent": True,
        }],
    )
    other = FakeNodeClient(metrics(20, 20), [{"job_id": "duplicate", "status": "running"}])
    queue = make_queue(tmp_path, {"first": possible_execution, "other": other})

    job = queue.submit("python work.py")

    assert job["status"] == "unknown"
    assert "not retried" in job["error"]
    assert len(possible_execution.started) == 1
    assert other.started == []


def test_submit_does_not_retry_a_node_policy_rejection(tmp_path):
    rejected = FakeNodeClient(
        metrics(5, 10),
        [{"job_id": None, "status": "blocked", "stderr": "Command blocked"}],
    )
    other = FakeNodeClient(metrics(20, 20), [{"job_id": "duplicate", "status": "running"}])
    queue = make_queue(tmp_path, {"first": rejected, "other": other})

    job = queue.submit("blocked command")

    assert job["status"] == "failed"
    assert job["error"] == "Command blocked"
    assert other.started == []


def test_status_refreshes_remote_job_and_cancel_updates_local_record(tmp_path):
    client = FakeNodeClient(
        metrics(20, 20),
        [{"job_id": "remote-job", "status": "running"}],
        check_result={"status": "completed", "exit_code": 0, "stdout": "done"},
    )
    queue = make_queue(tmp_path, {"node": client})
    submitted = queue.submit("echo done")

    completed = queue.get_job(submitted["id"])
    assert completed["status"] == "completed"
    assert completed["stdout"] == "done"
    assert client.checked == ["remote-job"]

    running_client = FakeNodeClient(
        metrics(20, 20), [{"job_id": "running-job", "status": "running"}]
    )
    running_queue = make_queue(tmp_path / "running", {"node": running_client})
    running = running_queue.submit("long task")
    cancelled = running_queue.cancel(running["id"])

    assert cancelled["success"] is True
    assert cancelled["job"]["status"] == "cancelled"
    assert running_client.killed == ["running-job"]


def test_invalid_ids_and_empty_commands_are_rejected(tmp_path):
    queue = make_queue(tmp_path, {})

    assert queue.get_job("../secrets") is None
    with pytest.raises(ValueError, match="non-empty"):
        queue.submit("  ")
    with pytest.raises(ValueError, match="positive integer"):
        queue.submit("echo test", timeout=0)


def test_queue_cli_passes_the_command_to_its_handler(monkeypatch, capsys):
    import main

    monkeypatch.setattr(
        sys, "argv", ["cloudmesh", "queue", "submit", "--timeout", "0", "echo test"]
    )

    with pytest.raises(SystemExit) as exc:
        main.main()

    assert exc.value.code == 2
    output = capsys.readouterr()
    assert "Timeout must be a positive integer" in output.out + output.err


@pytest.mark.parametrize(
    ("node", "expected_status"),
    [(None, "failed"), ("node", "unknown")],
)
def test_stale_dispatch_record_is_resolved_conservatively(
    tmp_path, node, expected_status
):
    queue = make_queue(tmp_path, {"node": FakeNodeClient(metrics(20, 20))})
    job_id = "0123456789ab"
    queue._save_job({
        "id": job_id,
        "command": "long task",
        "status": "dispatching",
        "node": node,
        "node_job_id": None,
        "created_at": (datetime.now() - timedelta(minutes=2)).isoformat(),
        "dispatch_started_at": (datetime.now() - timedelta(minutes=2)).isoformat(),
        "attempts": [],
    })

    job = queue.get_job(job_id)

    assert job["status"] == expected_status
