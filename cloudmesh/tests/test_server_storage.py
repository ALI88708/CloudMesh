"""Wiring tests: ServerManager/GroupsManager share state with StorageManager."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from cloudmesh.core.groups import GroupsManager
    from cloudmesh.core.security import SecurityManager
    from cloudmesh.core.server import ServerManager
    from cloudmesh.core.storage import StorageManager
except ImportError:
    from core.groups import GroupsManager
    from core.security import SecurityManager
    from core.server import ServerManager
    from core.storage import StorageManager


def _managers(tmp_path):
    security = SecurityManager(base_dir=str(tmp_path))
    storage = StorageManager(tmp_path)
    return security, storage


def test_server_added_via_manager_visible_in_storage(tmp_path):
    security, storage = _managers(tmp_path)
    mgr = ServerManager(security, storage)
    mgr.add_server("web1", "10.0.0.1", "root", 22, None, "s3cret")
    row = storage.get_server("web1")
    assert row is not None
    assert row["host"] == "10.0.0.1"
    assert row["password"] == "s3cret"  # decrypted on read
    assert "web1" in mgr.list_servers()
    assert mgr.get_server_info("web1")["host"] == "10.0.0.1"


def test_server_added_directly_to_storage_visible_to_manager(tmp_path):
    security, storage = _managers(tmp_path)
    assert storage.add_server("db1", "10.0.0.2", "admin", 2222, None, "pw")
    mgr = ServerManager(security, storage)
    assert "db1" in mgr.list_servers()
    assert mgr.get_server_info("db1")["port"] == 2222


def test_legacy_json_servers_imported_once(tmp_path):
    security, _ = _managers(tmp_path)
    security.save_config(
        {"servers": {"legacy": {"host": "10.0.0.9", "user": "root"}}}
    )
    mgr = ServerManager(security)  # default storage on same base_dir
    assert "legacy" in mgr.list_servers()
    assert mgr.storage.get_server("legacy")["host"] == "10.0.0.9"


def test_manager_remove_deletes_from_storage(tmp_path):
    security, storage = _managers(tmp_path)
    mgr = ServerManager(security, storage)
    mgr.add_server("tmp1", "10.0.0.3", "root")
    mgr.remove_server("tmp1")
    assert storage.get_server("tmp1") is None
    assert "tmp1" not in mgr.list_servers()
    with pytest.raises(ValueError):
        mgr.remove_server("tmp1")


def test_manager_duplicate_rejected(tmp_path):
    security, storage = _managers(tmp_path)
    mgr = ServerManager(security, storage)
    mgr.add_server("dup", "10.0.0.4", "root")
    with pytest.raises(ValueError):
        mgr.add_server("dup", "10.0.0.4", "root")


def test_groups_shared_between_manager_and_storage(tmp_path):
    security, storage = _managers(tmp_path)
    gm = GroupsManager(security, storage)
    gm.create_group("web")
    gm.add_to_group("web", "web1")
    assert storage.get_group_devices("web") == ["web1"]
    assert gm.get_group_devices("web") == ["web1"]
    # direct storage write visible to a fresh manager
    storage.create_group("db")
    storage.add_to_group("db", "db1", "server")
    gm2 = GroupsManager(security, storage)
    assert gm2.get_group_devices("db") == ["db1"]
    gm.delete_group("web")
    assert storage.list_groups().get("web") is None


def test_legacy_import_runs_once_and_empty_stays_empty(tmp_path):
    """After the marker is set, later JSON edits must not re-import."""
    security, storage = _managers(tmp_path)
    ServerManager(security, storage)  # marker set on empty state
    cfg = security.load_config()
    cfg["servers"]["sneaky"] = {"host": "1.2.3.4", "user": "root"}
    security.save_config(cfg)
    fresh = ServerManager(security, storage)
    assert "sneaky" not in fresh.list_servers()
    assert security.load_config().get("servers", {}) == {}


def test_restore_empty_backup_does_not_resurrect(tmp_path):
    """Empty server/group lists are valid: restore must win over JSON mirror."""
    security, storage = _managers(tmp_path)
    mgr = ServerManager(security, storage)
    gm = GroupsManager(security, storage)
    empty_backup = storage.backup_database()

    mgr.add_server("web1", "10.0.0.1", "root")
    gm.create_group("web")
    gm.add_to_group("web", "web1")

    assert storage.restore_backup(empty_backup) is True

    fresh_mgr = ServerManager(security, storage)
    fresh_gm = GroupsManager(security, storage)
    assert fresh_mgr.list_servers() == []
    assert fresh_gm.list_groups() == {}
    # JSON mirrors repaired from SQLite (no stale resurrection data).
    disk = security.load_config()
    assert disk.get("servers", {}) == {}
    assert disk.get("groups", {}) == {}


def test_rename_group_updates_storage_and_fresh_manager(tmp_path):
    src = Path(__file__).resolve().parent.parent / "core" / "groups.py"
    assert src.read_text().count("def rename_group") == 1

    security, storage = _managers(tmp_path)
    gm = GroupsManager(security, storage)
    gm.create_group("old")
    gm.add_to_group("old", "dev1")
    gm.rename_group("old", "new")

    assert storage.get_group_devices("new") == ["dev1"]
    assert "old" not in storage.list_groups()
    fresh = GroupsManager(security, storage)
    assert fresh.get_group_devices("new") == ["dev1"]
    assert "old" not in fresh.list_groups()
    with pytest.raises(ValueError):
        gm.rename_group("missing", "other")
