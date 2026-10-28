import argparse

import pytest

from cloudmesh.core.drain import DrainRegistry
from cloudmesh.core.task_queue import SmartTaskQueue


class FakeNodeClient:
    def __init__(self, metrics):
        self.metrics = metrics
        self.started = []

    def get_metrics(self):
        return self.metrics

    def start_job(self, command, timeout):
        self.started.append((command, timeout))
        return {"job_id": f"job-{len(self.started)}", "status": "running"}

    def check_job(self, job_id):
        return {"status": "running"}

    def kill_job(self, job_id):
        return {"success": True}


def metrics(cpu=10, ram=10):
    return {"cpu_percent": cpu, "ram": {"percent": ram}}


def make_queue(tmp_path, clients, **kwargs):
    nodes = {
        name: {"host": name, "port": 9999, "key": name}
        for name in clients
    }
    return SmartTaskQueue(
        nodes,
        queue_dir=tmp_path,
        client_factory=lambda host, _port, _key: clients[host],
        **kwargs,
    )


def test_a_drained_node_is_remembered_across_instances(tmp_path):
    DrainRegistry(tmp_path).drain("gpu-1", reason="nvme swap")

    reopened = DrainRegistry(tmp_path)

    assert reopened.names() == {"gpu-1"}
    assert reopened.load()["gpu-1"]["reason"] == "nvme swap"


def test_undrain_removes_the_mark_and_reports_whether_it_was_there(tmp_path):
    registry = DrainRegistry(tmp_path)
    registry.drain("gpu-1")

    assert registry.undrain("gpu-1") is True
    assert registry.names() == set()
    assert registry.undrain("gpu-1") is False


def test_a_corrupt_drain_file_reads_as_empty(tmp_path):
    (tmp_path / ".node_drain.json").write_text("{not json", encoding="utf-8")

    assert DrainRegistry(tmp_path).names() == set()


def test_a_drained_node_receives_no_jobs(tmp_path):
    busy = FakeNodeClient(metrics(90, 90))
    quiet = FakeNodeClient(metrics(10, 10))
    queue = make_queue(tmp_path, {"busy": busy, "quiet": quiet}, drained={"quiet"})

    job = queue.submit("python work.py")
    queue.process_once()

    assert quiet.started == []
    assert busy.started == [("python work.py", 300)]
    assert queue.get_job(job["id"], refresh=False)["node"] == "busy"


def test_when_every_node_is_drained_the_job_says_so(tmp_path):
    queue = make_queue(
        tmp_path,
        {"web-1": FakeNodeClient(metrics()), "web-2": FakeNodeClient(metrics())},
        drained={"web-1", "web-2"},
    )

    job = queue.submit("python work.py")
    queue.process_once()

    stored = queue.get_job(job["id"], refresh=False)
    assert stored["status"] == "queued"
    assert "drained" in stored["last_error"].lower()


def test_the_drain_state_is_read_on_every_pass(tmp_path):
    state = {"web-1"}
    client = FakeNodeClient(metrics())
    queue = make_queue(
        tmp_path, {"web-1": client}, drained_provider=lambda: state
    )
    job = queue.submit("python work.py")

    assert queue.process_once()["dispatched"] == []

    state.clear()

    assert queue.process_once()["dispatched"] == [job["id"]]
    assert client.started == [("python work.py", 300)]


def test_a_failing_drain_provider_does_not_stop_the_queue(tmp_path):
    def broken():
        raise OSError("cannot read state")

    client = FakeNodeClient(metrics())
    queue = make_queue(tmp_path, {"web-1": client}, drained_provider=broken)

    job = queue.submit("python work.py")

    assert queue.process_once()["dispatched"] == [job["id"]]


class _Registry:
    def __init__(self):
        self.drained = {}
        self.undrained = []

    def drain(self, name, reason=None):
        self.drained[name] = {"reason": reason, "at": "2026-10-28T00:00:00"}
        return self.drained[name]

    def undrain(self, name):
        self.undrained.append(name)
        return True


def _node_args(name, reason=None):
    return argparse.Namespace(name=name, reason=reason)


def _wire_nodes(monkeypatch, names=("gpu-1",), reason=None):
    import cloudmesh.main as main_module

    registry = _Registry()
    monkeypatch.setattr(
        main_module, "_load_node_keys",
        lambda: {name: {"host": name, "port": 9999, "key": name} for name in names},
    )
    monkeypatch.setattr(main_module, "_drain_registry", lambda: registry)
    return main_module, registry


def test_cm_node_drain_rejects_an_unknown_node(monkeypatch):
    main_module, registry = _wire_nodes(monkeypatch)

    with pytest.raises(SystemExit) as exc:
        main_module.cmd_node_drain(_node_args("ghost"))

    assert exc.value.code == 2
    assert registry.drained == {}


def test_cm_node_drain_records_the_reason(monkeypatch):
    main_module, registry = _wire_nodes(monkeypatch)

    main_module.cmd_node_drain(_node_args("gpu-1", reason="nvme swap"))

    assert registry.drained == {
        "gpu-1": {"reason": "nvme swap", "at": "2026-10-28T00:00:00"}
    }


def test_cm_node_undrain_calls_undrain(monkeypatch):
    main_module, registry = _wire_nodes(monkeypatch)

    main_module.cmd_node_undrain(_node_args("gpu-1"))

    assert registry.undrained == ["gpu-1"]
