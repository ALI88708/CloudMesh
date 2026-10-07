"""Tests for drift detection and smart diagnostics (fully offline)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from cloudmesh.core.diagnose import DiagnoseEngine
    from cloudmesh.core.drift import DriftManager
    from cloudmesh.core.storage import StorageManager
except ImportError:
    from core.diagnose import DiagnoseEngine
    from core.drift import DriftManager
    from core.storage import StorageManager


class _Monitor:
    def __init__(self, metrics):
        """Store the per-server metrics this fake monitor will return."""
        self._metrics = metrics

    def get_local_metrics(self):
        """Return the canned metrics for the local server."""
        return self._metrics["local"]

    def get_all_metrics(self, name):
        """Return the canned metrics for a named server, or raise if unknown."""
        if name not in self._metrics:
            raise ValueError(f"unknown server {name}")
        return self._metrics[name]


class _Servers:
    def __init__(self, names):
        """Store the fixed list of server names this fake will report."""
        self._names = names

    def list_servers(self):
        """Return a copy of the fixed server name list."""
        return list(self._names)


def _metrics(cpu=10.0, ram=20.0, disk=30.0):
    """Build a fake metrics dict with the given CPU, RAM, and disk percentages."""
    return {
        "cpu_percent": cpu,
        "ram": {"used_gb": 1.6, "total_gb": 8.0, "percent": ram},
        "disk": {"used_gb": 30.0, "total_gb": 100.0, "percent": disk},
    }


# -- drift ---------------------------------------------------------------

def test_drift_snapshot_check_clean(tmp_path):
    """A snapshot taken right before check() must report no drift."""
    dm = DriftManager(storage=StorageManager(tmp_path))
    dm.storage.add_server("web1", "10.0.0.1", "root")
    dm.snapshot()
    result = dm.check()
    assert result["has_baseline"] is True
    assert result["drifted"] is False


def test_drift_detects_added_removed_modified(tmp_path):
    """Adding, removing, and creating resources after a snapshot must show up as drift."""
    dm = DriftManager(storage=StorageManager(tmp_path))
    dm.storage.add_server("web1", "10.0.0.1", "root")
    dm.storage.create_group("g1")
    dm.snapshot()
    dm.storage.add_server("web2", "10.0.0.2", "root")
    dm.storage.remove_server("web1")
    dm.storage.create_group("g2")
    result = dm.check()
    assert result["drifted"] is True
    assert result["diff"]["servers"]["added"] == ["web2"]
    assert result["diff"]["servers"]["removed"] == ["web1"]
    assert result["diff"]["groups"]["added"] == ["g2"]
    assert dm.summarize(result["diff"])


def test_drift_no_baseline(tmp_path):
    """Checking before any snapshot must report no baseline and no drift."""
    dm = DriftManager(storage=StorageManager(tmp_path))
    result = dm.check()
    assert result == {"has_baseline": False, "drifted": False, "diff": {}}


def test_drift_collection_failure_never_reports_removals(tmp_path):
    """A storage read failure must surface as an error, never as false removals."""
    from cloudmesh.core.drift import DriftError
    real = StorageManager(tmp_path)
    dm = DriftManager(storage=real)
    dm.storage.add_server("web1", "10.0.0.1", "root")
    dm.snapshot()

    class _FlakyLists:
        """Settings work, but every collection read fails."""

        def __init__(self, inner):
            """Wrap a real storage manager whose list_* reads will be broken."""
            self._inner = inner

        def __getattr__(self, name):
            """Raise on any list_* read; delegate everything else to the inner storage."""
            if name.startswith("list_"):
                raise RuntimeError("db unreadable")
            return getattr(self._inner, name)

    broken = DriftManager(server_mgr=None, storage=_FlakyLists(real))
    with pytest.raises(DriftError):
        broken.collect()
    with pytest.raises(DriftError):
        broken.snapshot()
    result = broken.check()
    assert result["has_baseline"] is True
    assert result["drifted"] is False
    assert result.get("error")
    assert result["diff"] == {}
    # baseline untouched by the refused snapshot
    assert dm.get_baseline()["servers"] == {
        "web1": {"host": "10.0.0.1", "user": "root", "port": 22}}


def test_drift_excludes_secrets(tmp_path):
    """A drift snapshot must never contain a node's raw auth key."""
    dm = DriftManager(storage=StorageManager(tmp_path))
    dm.storage.add_node("n1", "10.0.0.5", 9999, "supersecret-auth-key")
    state = dm.snapshot()
    blob = str(state)
    assert "supersecret-auth-key" not in blob


# -- diagnose ------------------------------------------------------------

def test_diagnose_healthy_reports_info(tmp_path):
    """A healthy system must still produce findings, all at info level or above."""
    engine = DiagnoseEngine(
        monitor=_Monitor({"local": _metrics()}),
        server_mgr=_Servers([]),
        storage=StorageManager(tmp_path),
        base_dir=str(tmp_path),
    )
    findings = engine.diagnose()
    assert findings
    assert all(f["severity"] in ("info", "warning", "critical") for f in findings)


def test_diagnose_flags_critical_disk_and_ram():
    """Disk, RAM, and CPU usage near 100% must be flagged critical with suggestions."""
    engine = DiagnoseEngine(
        monitor=_Monitor({"local": _metrics(cpu=99.0, ram=95.0, disk=97.0)}),
        server_mgr=_Servers([]),
        storage=None,
        base_dir=None,
    )
    by_id = {f["id"]: f for f in engine.diagnose()}
    assert by_id["disk-critical"]["severity"] == "critical"
    assert by_id["ram-critical"]["severity"] == "critical"
    assert by_id["cpu-critical"]["severity"] == "critical"
    assert "cm cleanup" in by_id["disk-critical"]["suggestion"]
    assert "cm top" in by_id["ram-critical"]["suggestion"]


def test_diagnose_unreachable_server_warns():
    """A server that can't be reached must produce a warning finding naming it."""
    engine = DiagnoseEngine(
        monitor=_Monitor({"local": _metrics()}),
        server_mgr=_Servers(["ghost"]),
        storage=None,
        base_dir=None,
    )
    by_id = {f["id"]: f for f in engine.diagnose()}
    assert by_id["unreachable"]["severity"] == "warning"
    assert "ghost" in by_id["unreachable"]["title"]


def test_diagnose_includes_drift_findings(tmp_path):
    """Diagnose output must include a drift finding naming the new server."""
    dm = DriftManager(storage=StorageManager(tmp_path))
    dm.storage.add_server("web1", "10.0.0.1", "root")
    dm.snapshot()
    dm.storage.add_server("web2", "10.0.0.2", "root")
    engine = DiagnoseEngine(
        monitor=_Monitor({"local": _metrics()}),
        server_mgr=_Servers([]),
        storage=dm.storage,
        base_dir=str(tmp_path),
        drift=dm,
    )
    drift_hits = [f for f in engine.diagnose() if f["id"] == "drift"]
    assert drift_hits
    assert "web2" in drift_hits[0]["title"]


def test_diagnose_without_components_never_raises(tmp_path):
    """DiagnoseEngine with no components wired in must still return a list."""
    engine = DiagnoseEngine()
    findings = engine.diagnose()
    assert isinstance(findings, list)


def test_diagnose_without_storage_skips_drift_silently(tmp_path, monkeypatch):
    """Without storage, diagnose must skip drift checks and touch no files."""
    monkeypatch.chdir(tmp_path)
    engine = DiagnoseEngine(monitor=_Monitor({"local": {
        "cpu_percent": 5.0,
        "ram": {"used_gb": 1.0, "total_gb": 8.0, "percent": 12.0},
        "disk": {"used_gb": 10.0, "total_gb": 100.0, "percent": 10.0},
    }}))
    findings = engine.diagnose()
    assert not [f for f in findings if f["area"] == "drift"]
    assert list(tmp_path.iterdir()) == []
