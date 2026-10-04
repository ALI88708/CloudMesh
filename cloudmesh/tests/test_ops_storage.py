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


def test_doctor_reports_storage_checks(capsys):
    try:
        import cloudmesh.main as cloudmesh_main
    except ImportError:
        import main as cloudmesh_main
    cloudmesh_main.cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert "Storage" in out
