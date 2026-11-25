"""CloudMesh 5.0: the server registry is SQLite-only.

Earlier versions imported a JSON server list once and then kept rewriting it as
a compatibility mirror. That meant two writable sources of truth and repeated
encrypted-config writes during fleet execution. Version 5 imports legacy JSON
once, removes it, and never falls back to it again.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloudmesh.core.security import SecurityManager
from cloudmesh.core.server import ServerManager
from cloudmesh.core.storage import StorageManager


def _managers(tmp_path):
    """Build security and storage managers in an isolated directory."""
    return SecurityManager(base_dir=str(tmp_path)), StorageManager(tmp_path)


def test_adding_a_server_does_not_write_a_json_server_registry(tmp_path):
    """SQLite is the only writable server registry after the change."""
    security, storage = _managers(tmp_path)
    manager = ServerManager(security, storage)

    manager.add_server("web-1", "10.0.0.1", "root", password="secret")

    assert manager.list_servers() == ["web-1"]
    assert manager.get_server_info("web-1")["host"] == "10.0.0.1"
    assert "servers" not in security.load_config()


def test_legacy_json_is_imported_once_and_then_removed(tmp_path):
    """Existing 4.x installs migrate without losing their servers."""
    security, _ = _managers(tmp_path)
    security.save_config(
        {"servers": {"legacy": {"host": "10.0.0.9", "user": "root"}}}
    )

    manager = ServerManager(security)

    assert manager.storage.get_server("legacy")["host"] == "10.0.0.9"
    assert "servers" not in security.load_config()


def test_json_edits_after_migration_are_ignored_and_removed(tmp_path):
    """A hand-edited legacy file can no longer resurrect a deleted server."""
    security, storage = _managers(tmp_path)
    ServerManager(security, storage)
    config = security.load_config()
    config["servers"] = {"sneaky": {"host": "1.2.3.4", "user": "root"}}
    security.save_config(config)

    fresh = ServerManager(security, storage)

    assert "sneaky" not in fresh.list_servers()
    assert "servers" not in security.load_config()


def test_status_updates_never_recreate_the_json_registry(tmp_path):
    """Fleet connections must not write the old mirror back into config.json."""
    security, storage = _managers(tmp_path)
    manager = ServerManager(security, storage)
    manager.add_server("web-1", "10.0.0.1", "root")

    manager._set_status("web-1", "connected")

    assert storage.get_server("web-1")["status"] == "connected"
    assert "servers" not in security.load_config()


class _UnavailableStorage:
    """Simulate a database that cannot answer registry queries."""

    def list_servers(self):
        """Fail the way an unavailable database would."""
        raise OSError("database unavailable")

    def get_server(self, name):
        """Report no readable record."""
        return None


def test_doctor_requires_an_empty_or_absent_legacy_registry(tmp_path):
    """Doctor validates the v5 invariant instead of comparing two mirrors."""
    from cloudmesh.main import _server_registry_check

    security, storage = _managers(tmp_path)
    manager = ServerManager(security, storage)
    manager.add_server("web-1", "10.0.0.1", "root")

    ok, detail = _server_registry_check(security, storage)
    assert ok is True
    assert "sqlite=1" in detail

    config = security.load_config()
    config["servers"] = {"stale": {"host": "10.0.0.8", "user": "root"}}
    security.save_config(config)
    ok, detail = _server_registry_check(security, storage)
    assert ok is False
    assert "legacy JSON" in detail


def test_doctor_checks_the_registry_in_the_configured_data_directory(
    tmp_path, monkeypatch, capsys
):
    """CLOUDMESH_DIR must select the database doctor inspects."""
    from argparse import Namespace
    from cloudmesh.main import cmd_doctor

    data_dir = tmp_path / "data"
    source_dir = tmp_path / "source"
    data_dir.mkdir()
    source_dir.mkdir()
    monkeypatch.setenv("CLOUDMESH_DIR", str(data_dir))
    security, storage = _managers(data_dir)
    manager = ServerManager(security, storage)
    manager.add_server("web-1", "10.0.0.1", "root")

    cmd_doctor(Namespace(base_dir=str(source_dir)))

    output = capsys.readouterr().out
    registry_lines = [
        line for line in output.splitlines() if "Storage: server registry" in line
    ]
    assert registry_lines
    assert "PASS" in registry_lines[0]
    assert "sqlite=1" in output


def test_storage_failure_does_not_fall_back_to_json(tmp_path):
    """A database error must not silently select a stale second registry."""
    security, _ = _managers(tmp_path)
    security.save_config(
        {"servers": {"stale": {"host": "10.0.0.8", "user": "root"}}}
    )
    manager = ServerManager(security, _UnavailableStorage())

    assert manager.list_servers() == []
    with pytest.raises(ValueError, match="not found"):
        manager.get_server_info("stale")
