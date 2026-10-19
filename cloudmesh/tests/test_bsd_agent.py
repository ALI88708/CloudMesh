import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "node"))
import cloudmesh_node


@pytest.mark.parametrize(
    "system,expected",
    [
        ("FreeBSD", "freebsd"),
        ("OpenBSD", "openbsd"),
        ("NetBSD", "netbsd"),
        ("Linux", "linux"),
        ("Windows", "windows"),
        ("SunOS", "linux"),
    ],
)
def test_system_os_type(monkeypatch, system, expected):
    monkeypatch.setattr(cloudmesh_node.platform, "system", lambda: system)
    assert cloudmesh_node._system_os_type() == expected


def test_resolve_written_path_without_proc(monkeypatch, tmp_path):
    target = tmp_path / "data" / "jobs.json"
    target.parent.mkdir()
    target.write_text("{}")
    monkeypatch.setattr(Path, "exists", lambda self: False)
    resolved = cloudmesh_node._resolve_written_path(123, str(target))
    assert resolved == Path(str(target)).resolve()


def test_spa_guard_refuses_non_linux():
    freebsd = cloudmesh_node._spa_guard("FreeBSD")
    assert freebsd and "not supported" in freebsd.lower()
    assert "not supported" in cloudmesh_node._spa_guard("Windows").lower()
    assert cloudmesh_node._spa_guard("Linux") is None


def test_collect_metrics_falls_back_to_vmstat_and_sysctl(monkeypatch):
    class FakeResult:
        def __init__(self, stdout):
            self.stdout = stdout
            self.returncode = 0

    def fake_run(cmd, **kwargs):
        if cmd[0] == "vmstat":
            return FakeResult(" r b w avm fre\n 1 0 0 1 1\n 0 0 0 1 1 25\n")
        return FakeResult("8589934592 4096 500000\n")

    monkeypatch.setattr(cloudmesh_node, "HAS_PSUTIL", False)
    monkeypatch.setattr(cloudmesh_node.platform, "system", lambda: "FreeBSD")
    monkeypatch.setattr(cloudmesh_node.subprocess, "run", fake_run)
    monkeypatch.setattr(cloudmesh_node, "get_gpu_info", lambda: {})
    metrics = cloudmesh_node._collect_metrics()
    assert metrics["cpu_percent"] == 75.0
    assert metrics["ram"]["total_gb"] == 8.0
    assert metrics["ram"]["free_gb"] == 1.9
