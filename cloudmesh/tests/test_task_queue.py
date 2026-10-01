from datetime import datetime, timedelta
import sys
from pathlib import Path

import pytest

from core.task_queue import SmartTaskQueue
from core.task_queue import WorkerAlreadyRunningError

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
    saved = queue.get_job(job["id"], refresh=False)
    assert saved["node"] == "available"


def test_scheduler_prefers_nodes_with_more_free_disk_space(tmp_path):
    small_disk = FakeNodeClient(
        {
            "cpu_percent": 20,
            "ram": {"percent": 20},
            "disk": {"percent": 90, "free_gb": 5},
        },
        [{"job_id": "small-job", "status": "running"}],
    )
    large_disk = FakeNodeClient(
        {
            "cpu_percent": 20,
            "ram": {"percent": 20},
            "disk": {"percent": 20, "free_gb": 80},
        },
        [{"job_id": "large-job", "status": "running"}],
    )
    queue = make_queue(
        tmp_path, {"small-disk": small_disk, "large-disk": large_disk}
    )

    job = queue.submit("download and unpack", min_disk_free_gb=30)
    queue.process_once()

    assert queue.get_job(job["id"], refresh=False)["node"] == "large-disk"
    assert small_disk.started == []
    assert large_disk.started == [("download and unpack", 300)]


def test_threshold_only_jobs_keep_legacy_same_pass_reservations(tmp_path):
    node = FakeNodeClient(
        {"cpu_percent": 0, "ram": {"percent": 0}, "disk": {"free_gb": 100}},
        [{"job_id": "first", "status": "running"}],
    )
    queue = make_queue(tmp_path, {"node": node})
    first = queue.submit("first", priority=5, min_disk_free_gb=60)
    second = queue.submit("second", priority=1, min_disk_free_gb=60)

    summary = queue.process_once()

    assert summary["dispatched"] == [first["id"]]
    assert summary["queued"] == 1
    assert queue.get_job(second["id"], refresh=False)["status"] == "queued"


@pytest.mark.parametrize(
    ("claim_kwargs", "claim_key", "claim_value"),
    [
        ({"cpu_claim_percent": 60}, "cpu_claim_percent", 60),
        ({"ram_claim_gb": 10}, "ram_claim_gb", 10),
        ({"disk_claim_gb": 30}, "disk_claim_gb", 30),
    ],
)
def test_explicit_resource_claims_reserve_same_pass_node_capacity(
    tmp_path, claim_kwargs, claim_key, claim_value
):
    node = FakeNodeClient(
        {
            "cpu_percent": 0,
            "ram": {"percent": 0, "free_gb": 16},
            "disk": {"free_gb": 50},
        },
        [{"job_id": "first", "status": "running"}],
    )
    queue = make_queue(tmp_path, {"node": node})
    first = queue.submit("first", priority=5, **claim_kwargs)
    second = queue.submit("second", priority=1, **claim_kwargs)

    summary = queue.process_once()

    assert summary["dispatched"] == [first["id"]]
    assert summary["queued"] == 1
    assert queue.get_job(second["id"], refresh=False)["status"] == "queued"
    assert [command for command, _ in node.started] == ["first"]
    saved = queue.get_job(first["id"], refresh=False)
    assert saved["requirements"][claim_key] == claim_value


def test_explicit_claims_are_independent_of_minimum_free_thresholds(tmp_path):
    node = FakeNodeClient(
        {"cpu_percent": 0, "ram": {"percent": 0, "free_gb": 16}},
        [
            {"job_id": "first", "status": "running"},
            {"job_id": "second", "status": "running"},
        ],
    )
    queue = make_queue(tmp_path, {"node": node})
    first = queue.submit(
        "first", priority=5, min_ram_free_gb=12, ram_claim_gb=4
    )
    second = queue.submit(
        "second", priority=1, min_ram_free_gb=12, ram_claim_gb=4
    )

    summary = queue.process_once()

    assert summary["dispatched"] == [first["id"], second["id"]]
    assert [command for command, _ in node.started] == ["first", "second"]


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


def test_idempotent_running_job_fails_over_after_node_outage_grace(tmp_path):
    failed_node = FakeNodeClient(
        metrics(10, 10),
        [{"job_id": "first-attempt", "status": "running"}],
        check_result={
            "type": "error",
            "message": "Connection refused",
            "request_sent": False,
        },
    )
    backup_node = FakeNodeClient(
        metrics(10, 10), [{"job_id": "retry-attempt", "status": "running"}]
    )
    queue = SmartTaskQueue(
        {
            "a-node": {"host": "a-node", "key": "key"},
            "z-node": {"host": "z-node", "key": "key"},
        },
        queue_dir=tmp_path,
        client_factory=lambda host, _port, _key: {
            "a-node": failed_node,
            "z-node": backup_node,
        }[host],
        failover_grace_seconds=0,
    )
    job = queue.submit("python repeatable.py", idempotent=True)
    queue.process_once()

    running = queue.get_job(job["id"], refresh=False)
    running["unreachable_since"] = (
        datetime.now() - timedelta(seconds=1)
    ).isoformat()
    queue._save_job(running)

    assert queue.get_job(job["id"])["status"] == "queued"
    summary = queue.process_once()

    retried = queue.get_job(job["id"], refresh=False)
    assert summary["dispatched"] == [job["id"]]
    assert retried["status"] == "running"
    assert retried["node"] == "z-node"
    assert retried["retry_count"] == 1
    assert retried["node_job_id"] == "retry-attempt"
    assert [attempt["status"] for attempt in retried["attempts"]] == [
        "accepted",
        "retry_scheduled",
        "accepted",
    ]
    assert failed_node.started == [("python repeatable.py", 300)]
    assert backup_node.started == [("python repeatable.py", 300)]


def test_non_idempotent_outage_is_unknown_and_can_later_be_resolved(tmp_path):
    node = FakeNodeClient(
        metrics(10, 10),
        [{"job_id": "first-attempt", "status": "running"}],
        check_result={
            "type": "error",
            "message": "Connection refused",
            "request_sent": False,
        },
    )
    queue = SmartTaskQueue(
        {"node": {"host": "node", "key": "key"}},
        queue_dir=tmp_path,
        client_factory=lambda host, _port, _key: node,
        failover_grace_seconds=0,
    )
    job = queue.submit("python one-shot.py")
    queue.process_once()

    running = queue.get_job(job["id"], refresh=False)
    running["unreachable_since"] = (
        datetime.now() - timedelta(seconds=1)
    ).isoformat()
    queue._save_job(running)

    uncertain = queue.get_job(job["id"])
    assert uncertain["status"] == "unknown"
    assert "not replayed" in uncertain["error"]
    assert len(uncertain["attempts"]) == 2
    assert queue.get_job(job["id"])["attempts"] == uncertain["attempts"]
    assert node.started == [("python one-shot.py", 300)]

    node.check_result = {"status": "completed", "exit_code": 0}
    assert queue.get_job(job["id"])["status"] == "completed"


def test_queue_worker_exclusively_coordinates_a_shared_state_directory(tmp_path):
    queue = make_queue(tmp_path, {})

    with queue._worker_lock():
        with pytest.raises(WorkerAlreadyRunningError, match="already coordinates"):
            queue.run_worker(once=True)


def test_queue_directory_can_be_configured_by_environment(tmp_path, monkeypatch):
    shared_queue = tmp_path / "coordinator-state"
    monkeypatch.setenv("CLOUDMESH_QUEUE_DIR", str(shared_queue))

    queue = SmartTaskQueue({})

    assert queue.queue_dir == shared_queue
    assert shared_queue.is_dir()


def test_worker_recovers_stale_dispatching_jobs(tmp_path):
    queue = make_queue(tmp_path, {})
    job = queue.submit("python interrupted.py")
    job["status"] = "dispatching"
    job["node"] = "node-that-may-have-accepted"
    job["dispatch_started_at"] = (
        datetime.now() - timedelta(seconds=61)
    ).isoformat()
    queue._save_job(job)

    queue.process_once()

    recovered = queue.get_job(job["id"], refresh=False)
    assert recovered["status"] == "unknown"
    assert "may have received the job" in recovered["error"]


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
    with pytest.raises(ValueError, match="Minimum free disk"):
        queue.submit("echo test", min_disk_free_gb=-1)
    with pytest.raises(ValueError, match="CPU claim"):
        queue.submit("echo test", cpu_claim_percent=101)
    with pytest.raises(ValueError, match="RAM claim"):
        queue.submit("echo test", ram_claim_gb=-1)
    with pytest.raises(ValueError, match="Disk claim"):
        queue.submit("echo test", disk_claim_gb=-1)


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
