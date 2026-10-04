"""Wiring tests: nodes, alerts, schedules, templates, aliases share SQLite."""

import argparse
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from cloudmesh.core.alerts import AlertManager
    from cloudmesh.core.advanced import ScheduleManager, TemplateManager
    from cloudmesh.core.features import create_alias, get_aliases, remove_alias
    from cloudmesh.core.nodekeyring import NodeKeyring
    from cloudmesh.core.storage import StorageManager
except ImportError:
    from core.alerts import AlertManager
    from core.advanced import ScheduleManager, TemplateManager
    from core.features import create_alias, get_aliases, remove_alias
    from core.nodekeyring import NodeKeyring
    from core.storage import StorageManager


class _Monitor:
    def get_all_metrics(self, name):
        return None


def test_node_keyring_roundtrip_and_mirror(tmp_path):
    ring = NodeKeyring(storage=StorageManager(tmp_path), json_path=tmp_path / ".node_keys.json")
    ring.save({"n1": {"host": "10.0.0.1", "port": 9999, "key": "k1"},
               "n2": {"host": "10.0.0.2", "port": 9998, "key": "k2", "tls": True}})
    keys = ring.load()
    assert keys["n1"]["key"] == "k1"
    assert keys["n2"]["tls"] is True
    # secrets encrypted at rest, mirror present
    raw = (tmp_path / "cloudmesh.db").read_bytes()
    assert b"k1" not in raw
    mirror = json.loads((tmp_path / ".node_keys.json").read_text())
    assert mirror["n1"]["host"] == "10.0.0.1"
    # delete propagates
    ring.save({"n1": keys["n1"]})
    assert "n2" not in ring.load()


def test_node_keyring_legacy_import_and_empty_stays_empty(tmp_path):
    (tmp_path / ".node_keys.json").write_text(
        json.dumps({"legacy": {"host": "10.0.0.9", "port": 9999, "key": "lk"}}))
    ring = NodeKeyring(storage=StorageManager(tmp_path), json_path=tmp_path / ".node_keys.json")
    assert ring.load()["legacy"]["key"] == "lk"
    # empty table after deleting everything is valid: no resurrection
    ring.save({})
    assert ring.load() == {}
    ring2 = NodeKeyring(storage=ring.storage, json_path=tmp_path / ".node_keys.json")
    assert ring2.load() == {}


def test_alerts_wired_to_storage(tmp_path):
    mgr = AlertManager(_Monitor(), base_dir=str(tmp_path))
    mgr.add_rule("cpu-high", "cpu", 80.0, server="web1")
    rules = mgr.list_rules()
    assert any(r["name"] == "cpu-high" for r in rules)
    store = StorageManager(tmp_path)
    assert any(r["name"] == "cpu-high" for r in store.list_alert_rules())
    mgr.remove_rule("cpu-high")
    assert store.list_alert_rules() == []
    # fresh manager sees empty (no resurrection)
    assert AlertManager(_Monitor(), base_dir=str(tmp_path)).list_rules() == []


def test_alerts_legacy_import(tmp_path):
    (tmp_path / "alerts.json").write_text(json.dumps({
        "rules": [{"name": "old-rule", "metric": "ram", "threshold": 90}],
        "history": [], "last_notified": {},
    }))
    mgr = AlertManager(_Monitor(), base_dir=str(tmp_path))
    assert any(r["name"] == "old-rule" for r in mgr.list_rules())


def test_schedules_templates_wired(tmp_path):
    sm = ScheduleManager(schedule_file=str(tmp_path / ".schedule.json"),
                         storage=StorageManager(tmp_path), base_dir=str(tmp_path))
    sm.add("nightly", "cm backup", interval_seconds=86400, server="db1")
    assert "nightly" in sm.list_all()
    store = StorageManager(tmp_path)
    rows = {s["name"]: s for s in store.list_schedules()}
    assert rows["nightly"]["server"] == "db1"
    sm.toggle("nightly")
    assert sm.list_all()["nightly"]["enabled"] is False
    sm.remove("nightly")
    assert sm.list_all() == {}

    tm = TemplateManager(templates_file=str(tmp_path / ".templates.json"),
                         storage=store, base_dir=str(tmp_path))
    tm.add("deploy", "cm deploy {app}", description="deploy app")
    assert tm.get("deploy")["description"] == "deploy app"
    assert tm.render("deploy", app="web") == "cm deploy web"
    tm.remove("deploy")
    assert tm.list_all() == {}


def test_aliases_wired_with_legacy_import(tmp_path):
    f = tmp_path / ".aliases.json"
    f.write_text(json.dumps({"ll": "ls -la"}))
    store = StorageManager(tmp_path)
    assert get_aliases(aliases_file=str(f), storage=store)["ll"] == "ls -la"
    create_alias("gs", "git status", aliases_file=str(f), storage=store)
    assert store.list_aliases()["gs"] == "git status"
    assert remove_alias("gs", aliases_file=str(f), storage=store) is True
    assert remove_alias("nope", aliases_file=str(f), storage=store) is False
    # legacy JSON path untouched when storage not passed
    assert get_aliases(aliases_file=str(f))["ll"] == "ls -la"


def test_migrate_verify_ok_and_drift(tmp_path):
    try:
        from cloudmesh.core.migrate import MigrationManager
    except ImportError:
        from core.migrate import MigrationManager
    (tmp_path / ".aliases.json").write_text(json.dumps({"ll": "ls -la"}))
    (tmp_path / ".node_keys.json").write_text(json.dumps(
        {"n1": {"host": "10.0.0.1", "port": 9999, "key": "k"}}))
    mgr = MigrationManager(tmp_path)
    mgr.migrate_all(dry_run=False)
    result = MigrationManager(tmp_path).verify()
    assert result["ok"] is True, result
    # drift: JSON-only addition after migration
    aliases = json.loads((tmp_path / ".aliases.json").read_text())
    aliases["drift"] = "echo drift"
    (tmp_path / ".aliases.json").write_text(json.dumps(aliases))
    result2 = MigrationManager(tmp_path).verify()
    assert result2["ok"] is False
    assert any(c["type"] == "aliases" and not c["match"] for c in result2["checks"])


def test_doctor_reports_storage_checks(tmp_path, monkeypatch, capsys):
    try:
        import cloudmesh.main as cloudmesh_main
    except ImportError:
        import main as cloudmesh_main
    from cloudmesh.core import security

    security_manager = security.SecurityManager(base_dir=tmp_path)
    monkeypatch.setattr(security, "SecurityManager", lambda: security_manager)
    monkeypatch.setattr(cloudmesh_main, "__file__", str(tmp_path / "main.py"))
    monkeypatch.setattr(cloudmesh_main, "NODE_KEYS_FILE", tmp_path / ".node_keys.json")
    cloudmesh_main.cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert "Storage" in out


@pytest.mark.parametrize("contents", ["{broken", "[]", "null", '"text"'])
def test_node_keyring_ignores_invalid_legacy_document(tmp_path, contents):
    path = tmp_path / ".node_keys.json"
    path.write_text(contents)
    ring = NodeKeyring(base_dir=tmp_path)
    assert ring.load() == {}
    assert ring.storage.list_nodes() == []
    assert ring.storage.legacy_imported("nodes") is True


def test_node_keyring_updates_existing_node_and_removes_tls_options(tmp_path):
    ring = NodeKeyring(base_dir=tmp_path)
    ring.save({"edge": {"host": "old", "key": "old-secret", "tls": True,
                        "ca_file": "/certs/old.pem"}})
    expected = {"edge": {"host": "new", "port": 1234, "key": "new-secret"}}
    ring.save(expected)

    assert NodeKeyring(base_dir=tmp_path).load() == expected
    assert json.loads(ring.json_path.read_text()) == expected
    assert ring.storage.get_node("edge")["tls"] == 0
    assert ring.storage.get_node("edge")["ca_file"] is None
    assert len(ring.storage.list_nodes()) == 1


def test_node_keyring_import_skips_invalid_entries_and_preserves_tls(tmp_path):
    path = tmp_path / ".node_keys.json"
    path.write_text(json.dumps({
        "bad": "not a node", "missing-host": {"key": "invalid"},
        "good": {"host": "edge", "key": "secret", "tls": True,
                 "ca_file": "/certs/custom.pem"},
    }))
    ring = NodeKeyring(base_dir=tmp_path)
    assert ring.load() == {"good": {
        "host": "edge", "port": 9999, "key": "secret", "tls": True,
        "ca_file": "/certs/custom.pem",
    }}
    assert json.loads(path.read_text()) == ring.load()


def test_node_keyring_marked_empty_store_replaces_stale_mirror(tmp_path):
    store = StorageManager(tmp_path)
    store.mark_legacy_imported("nodes")
    path = tmp_path / ".node_keys.json"
    path.write_text(json.dumps({"deleted": {"host": "old", "key": "old"}}))
    assert NodeKeyring(storage=store).load() == {}
    assert json.loads(path.read_text()) == {}
    assert store.list_nodes() == []


def test_node_keyring_load_falls_back_to_mirror_on_storage_error(tmp_path, monkeypatch):
    from unittest.mock import Mock

    ring = NodeKeyring(base_dir=tmp_path)
    expected = {"edge": {"host": "edge", "port": 9999, "key": "secret"}}
    ring.save(expected)
    monkeypatch.setattr(ring.storage, "list_nodes", Mock(side_effect=OSError("offline")))
    assert ring.load() == expected


@pytest.mark.parametrize("kind", ["schedules", "templates"])
def test_manager_import_preserves_metadata_and_does_not_resurrect_deleted_rows(tmp_path, kind):
    store = StorageManager(tmp_path)
    if kind == "schedules":
        path = tmp_path / ".schedule.json"
        entry = {"command": "echo backup", "interval": 17, "enabled": False,
                 "server": "db", "created": "2026-01-02", "last_run": "2026-02-03",
                 "run_count": 12}
        def reopen():
            return ScheduleManager(schedule_file=path, storage=StorageManager(tmp_path))
    else:
        path = tmp_path / ".templates.json"
        entry = {"command": "echo {app}", "description": "deploy app", "created": "2026-01-02"}
        def reopen():
            return TemplateManager(templates_file=path, storage=StorageManager(tmp_path))
    path.write_text(json.dumps({"legacy": entry}))

    manager = reopen()
    assert manager.list_all() == {"legacy": entry}
    assert store.legacy_imported(kind) is True
    assert manager.remove("legacy") is True
    assert manager.remove("missing") is False
    # A restored/stale JSON file must not re-import rows after deletion.
    path.write_text(json.dumps({"legacy": entry}))
    assert reopen().list_all() == {}
    assert json.loads(path.read_text()) == {}


def test_schedule_toggle_persists_and_preserves_execution_metadata(tmp_path):
    path = tmp_path / ".schedule.json"
    store = StorageManager(tmp_path)
    store.upsert_schedule("job", "echo run", 60, server="db", created="2026-01-01",
                          last_run="2026-02-01", run_count=9)
    store.mark_legacy_imported("schedules")
    manager = ScheduleManager(schedule_file=path, storage=store)

    assert manager.toggle("missing") is False
    assert manager.toggle("job", False) is True
    reopened = ScheduleManager(schedule_file=path, storage=StorageManager(tmp_path))
    assert reopened.list_all()["job"] == {
        "command": "echo run", "interval": 60, "server": "db", "created": "2026-01-01",
        "last_run": "2026-02-01", "run_count": 9, "enabled": False,
    }
    assert reopened.toggle("job") is True
    assert store.list_schedules()[0]["enabled"] == 1
    assert json.loads(path.read_text())["job"]["enabled"] is True


def test_template_import_accepts_legacy_string_and_keeps_rendering_after_restart(tmp_path):
    path = tmp_path / ".templates.json"
    path.write_text(json.dumps({"old": "echo {app} {app} {unbound}"}))
    manager = TemplateManager(templates_file=path)
    assert manager.get("old") == {
        "command": "echo {app} {app} {unbound}", "description": "", "created": None,
    }
    manager.add("new", "echo {count}", "count things")
    reopened = TemplateManager(templates_file=path)
    assert reopened.render("old", app="web") == "echo web web {unbound}"
    assert reopened.render("new", count=0) == "echo 0"
    assert reopened.get("new")["description"] == "count things"
    assert reopened.get("new")["created"]
    assert reopened.render("missing") is None


@pytest.mark.parametrize("with_storage", [False, True])
def test_alias_normalization_update_and_removal(tmp_path, with_storage):
    path = tmp_path / ".aliases.json"
    path.write_text(json.dumps({"legacy": {"command": "echo old"}, "numeric": 42}))
    store = StorageManager(tmp_path) if with_storage else None
    assert get_aliases(path, storage=store) == {"legacy": "echo old", "numeric": "42"}
    assert create_alias("legacy", {"command": "echo new"}, path, storage=store) is True
    assert get_aliases(path, storage=store)["legacy"] == "echo new"
    assert json.loads(path.read_text()) == {"legacy": "echo new", "numeric": "42"}
    assert remove_alias("legacy", path, storage=store) is True
    assert remove_alias("numeric", path, storage=store) is True
    assert get_aliases(path, storage=store) == {}
    assert json.loads(path.read_text()) == {}


@pytest.mark.parametrize("contents", ["{broken", "[]", "null"])
def test_aliases_ignore_invalid_json_and_allow_new_alias(tmp_path, contents):
    path = tmp_path / ".aliases.json"
    path.write_text(contents)
    store = StorageManager(tmp_path)
    assert get_aliases(path, storage=store) == {}
    create_alias("new", "echo ok", path, storage=store)
    assert store.list_aliases() == {"new": "echo ok"}
    assert json.loads(path.read_text()) == {"new": "echo ok"}


def test_aliases_empty_database_does_not_return_stale_mirror(tmp_path):
    path = tmp_path / ".aliases.json"
    store = StorageManager(tmp_path)
    create_alias("deleted", "echo stale", path, storage=store)
    store.remove_alias("deleted")

    assert get_aliases(path, storage=StorageManager(tmp_path)) == {}


def test_alert_import_preserves_history_and_cooldowns_exactly_once(tmp_path):
    path = tmp_path / "alerts.json"
    path.write_text(json.dumps({
        "rules": [{"name": "cpu", "metric": "cpu", "threshold": 80,
                   "operator": "gte", "server": "web", "severity": "critical", "cooldown": 60}],
        "history": [{"rule": "cpu", "server": "web", "metric": "cpu", "value": 90,
                     "threshold": 80, "operator": "gte", "severity": "critical"}],
        "last_notified": {"cpu|web": 123.5, "malformed": 10},
    }))
    manager = AlertManager(_Monitor(), base_dir=tmp_path)
    reopened = AlertManager(_Monitor(), base_dir=tmp_path)
    assert len(reopened.list_rules()) == 1
    rule = reopened.list_rules()[0]
    assert (rule["operator"], rule["severity"], rule["cooldown"], rule["server"]) == (
        "gte", "critical", 60, "web",
    )
    assert len(reopened.get_history()) == 1
    history = reopened.get_history()[0]
    assert history["rule"] == "cpu"
    assert history["value"] == 90
    assert "rule_name" not in history
    assert reopened.storage.list_alert_cooldowns() == {"cpu|web": 123.5}
    assert json.loads(path.read_text())["history"] == reopened.get_history()
    manager.clear_history()
    assert reopened.get_history() == []
    assert json.loads(path.read_text())["history"] == []
    assert len(reopened.list_rules()) == 1
    assert reopened.storage.list_alert_cooldowns() == {"cpu|web": 123.5}


def test_alert_cooldown_survives_restart_and_expires_at_exact_boundary(tmp_path, monkeypatch):
    from unittest.mock import Mock
    import cloudmesh.core.alerts as alerts_module

    monitor = Mock()
    monitor.get_all_metrics.return_value = {"cpu_percent": 90}
    notifier = Mock()
    notifier.notify.return_value = {"test": True}
    monkeypatch.setattr(alerts_module.time, "time", lambda: 1000.0)
    manager = AlertManager(monitor, base_dir=tmp_path, notifier=notifier)
    manager.add_rule("cpu", "cpu", 80, server="web", cooldown=60)
    assert len(manager.check_alerts()) == 1
    notifier.notify.assert_called_once()

    reopened = AlertManager(monitor, base_dir=tmp_path, notifier=notifier)
    monkeypatch.setattr(alerts_module.time, "time", lambda: 1059.999)
    assert len(reopened.check_alerts()) == 1
    assert notifier.notify.call_count == 1
    assert reopened.storage.get_alert_cooldown("cpu", "web") == 1000.0
    monkeypatch.setattr(alerts_module.time, "time", lambda: 1060.0)
    assert len(reopened.check_alerts()) == 1
    assert notifier.notify.call_count == 2
    assert reopened.storage.get_alert_cooldown("cpu", "web") == 1060.0
    assert len(reopened.get_history()) == 3
    assert len(reopened.get_history(limit=2)) == 2
    mirror = json.loads((tmp_path / "alerts.json").read_text())
    assert len(mirror["history"]) == 3
    assert mirror["last_notified"] == {"cpu|web": 1060.0}


def test_alert_rule_normalization_is_persisted(tmp_path):
    manager = AlertManager(_Monitor(), base_dir=tmp_path)
    rule = manager.add_rule("cpu", "cpu", 80, severity="invalid", cooldown=-1)
    persisted = AlertManager(_Monitor(), base_dir=tmp_path).list_rules()[0]
    assert rule["severity"] == persisted["severity"] == "warning"
    assert rule["cooldown"] == persisted["cooldown"] == 0


@pytest.mark.parametrize("contents", ["{broken", "[]", "null"])
def test_alerts_invalid_legacy_document_starts_empty(tmp_path, contents):
    (tmp_path / "alerts.json").write_text(contents)
    manager = AlertManager(_Monitor(), base_dir=tmp_path)
    assert manager.list_rules() == []
    assert manager.get_history() == []
    assert manager.storage.legacy_imported("alerts") is True
