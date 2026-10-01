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

    assert job["status"] == "queued"
    assert available.started == []
    summary = queue.process_once()

    assert summary["dispatched"] == [job["id"]]
    stored = queue.get_job(job["id"], refresh=False)
    assert stored["status"] == "running"
    assert stored["node"] == "available"
    assert stored["node_job_id"] == "remote-job"
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
    queue.process_once()
    job = queue.get_job(job["id"], refresh=False)

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
    queue.process_once()
    job = queue.get_job(job["id"], refresh=False)

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
    queue.process_once()
    job = queue.get_job(job["id"], refresh=False)

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
    queue.process_once()

    completed = queue.get_job(submitted["id"])
    assert completed["status"] == "completed"
    assert completed["stdout"] == "done"
    assert client.checked == ["remote-job"]

    running_client = FakeNodeClient(
        metrics(20, 20), [{"job_id": "running-job", "status": "running"}]
    )
    running_queue = make_queue(tmp_path / "running", {"node": running_client})
    running = running_queue.submit("long task")
    running_queue.process_once()
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
    with pytest.raises(ValueError, match="Priority"):
        queue.submit("echo test", priority=10)
    with pytest.raises(ValueError, match="Minimum free CPU"):
        queue.submit("echo test", min_cpu_free_percent=101)
    with pytest.raises(ValueError, match="Minimum free RAM"):
        queue.submit("echo test", min_ram_free_gb=-1)


def test_worker_dispatches_higher_priority_jobs_first(tmp_path):
    node = FakeNodeClient(
        metrics(0, 0),
        [
            {"job_id": "high-job", "status": "running"},
            {"job_id": "normal-job", "status": "running"},
        ],
    )
    queue = make_queue(tmp_path, {"node": node})
    normal = queue.submit("normal", priority=2)
    high = queue.submit("high", priority=9)
    passes = []

    summary = queue.run_worker(once=True, on_pass=passes.append)

    assert summary["dispatched"] == [high["id"], normal["id"]]
    assert passes == [summary]
    assert [command for command, _ in node.started] == ["high", "normal"]


def test_worker_preserves_fifo_order_for_equal_priorities(tmp_path):
    node = FakeNodeClient(
        metrics(0, 0),
        [
            {"job_id": "first-job", "status": "running"},
            {"job_id": "second-job", "status": "running"},
        ],
    )
    queue = make_queue(tmp_path, {"node": node})
    first = queue.submit("first", priority=4)
    second = queue.submit("second", priority=4)
    first["created_at"] = "2024-01-01T00:00:00"
    second["created_at"] = "2024-01-01T00:00:01"
    queue._save_job(first)
    queue._save_job(second)

    summary = queue.process_once()

    assert summary["dispatched"] == [first["id"], second["id"]]
    assert [command for command, _ in node.started] == ["first", "second"]


def test_job_without_cpu_requirement_can_use_node_missing_cpu_metrics(tmp_path):
    node = FakeNodeClient(
        {"ram": {"percent": 10}},
        [{"job_id": "job", "status": "running"}],
    )
    queue = make_queue(tmp_path, {"node": node})
    job = queue.submit("run")

    summary = queue.process_once()

    assert summary["dispatched"] == [job["id"]]


def test_job_waits_until_node_meets_requested_resources(tmp_path):
    node_metrics = {
        "cpu_percent": 85,
        "ram": {"percent": 90, "free_gb": 1.5},
    }
    node = FakeNodeClient(node_metrics, [{"job_id": "job", "status": "running"}])
    queue = make_queue(tmp_path, {"node": node})
    job = queue.submit(
        "train",
        min_cpu_free_percent=20,
        min_ram_free_gb=2,
    )

    first_pass = queue.process_once()

    assert first_pass["dispatched"] == []
    assert first_pass["queued"] == 1
    assert queue.get_job(job["id"], refresh=False)["status"] == "queued"
    assert node.started == []

    node.metrics = {"cpu_percent": 40, "ram": {"percent": 40, "free_gb": 8}}
    second_pass = queue.process_once()

    assert second_pass["dispatched"] == [job["id"]]
    assert node.started == [("train", 300)]


def test_same_worker_pass_reserves_requested_cpu_capacity(tmp_path):
    node = FakeNodeClient(
        {"cpu_percent": 0, "ram": {"percent": 0, "free_gb": 32}},
        [
            {"job_id": "first", "status": "running"},
            {"job_id": "second", "status": "running"},
        ],
    )
    queue = make_queue(tmp_path, {"node": node})
    first = queue.submit("first", priority=5, min_cpu_free_percent=60)
    second = queue.submit("second", priority=1, min_cpu_free_percent=60)

    summary = queue.process_once()

    assert summary["dispatched"] == [first["id"]]
    assert summary["queued"] == 1
    assert queue.get_job(second["id"], refresh=False)["status"] == "queued"
    assert [command for command, _ in node.started] == ["first"]


def test_cancel_pending_job_without_contacting_a_node(tmp_path):
    node = FakeNodeClient(metrics(10, 10))
    queue = make_queue(tmp_path, {"node": node})
    job = queue.submit("wait for resources")

    result = queue.cancel(job["id"])

    assert result["success"] is True
    assert result["job"]["status"] == "cancelled"
    assert node.killed == []


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
