"""Regression coverage for PR #16 migration fidelity and verification."""

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from cloudmesh.core.migrate import MigrationManager
from cloudmesh.core.security import SecurityManager
from cloudmesh.core.storage import StorageManager


@pytest.mark.parametrize("kind", ["servers", "nodes", "groups"])
def test_verify_detects_name_drift_even_when_counts_match(tmp_path, kind):
    security = SecurityManager(base_dir=tmp_path)
    store = StorageManager(tmp_path)
    if kind == "nodes":
        (tmp_path / ".node_keys.json").write_text(json.dumps({"json-only": {"host": "edge"}}))
        store.add_node("db-only", "edge")
    elif kind == "servers":
        security.save_config({"servers": {"json-only": {"host": "web", "user": "root"}}})
        store.add_server("db-only", "web", "root")
    else:
        security.save_config({"groups": {"json-only": []}})
        store.create_group("db-only")

    result = MigrationManager(tmp_path).verify()

    check = next(check for check in result["checks"] if check["type"] == kind)
    assert result["ok"] is False
    assert result["errors"] == []
    assert check == {"type": kind, "json": ["json-only"], "sqlite": ["db-only"],
                     "match": False, "detail": "MISMATCH"}


@pytest.mark.parametrize("filename, content, kind", [
    ("alerts.json", {"rules": [{"name": "cpu"}]}, "alerts"),
    (".aliases.json", {"ll": "ls -l"}, "aliases"),
    (".templates.json", {"deploy": "echo deploy"}, "templates"),
    (".schedule.json", {"nightly": {"command": "echo run"}}, "schedules"),
    ("data/acl.json", {"users": {"viewer": {}}}, "acl_users"),
])
def test_verify_detects_count_drift_for_other_data_types(tmp_path, filename, content, kind):
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content))

    result = MigrationManager(tmp_path).verify()

    check = next(check for check in result["checks"] if check["type"] == kind)
    assert result["ok"] is False
    assert result["errors"] == []
    assert check == {"type": kind, "json": 1, "sqlite": 0,
                     "match": False, "detail": "MISMATCH"}


@pytest.mark.parametrize("filename", [".node_keys.json", ".aliases.json", "alerts.json",
                                      ".templates.json", ".schedule.json", "data/acl.json"])
def test_verify_reports_malformed_json_instead_of_success_for_empty_counts(tmp_path, filename):
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken")

    result = MigrationManager(tmp_path).verify()

    assert result["ok"] is False
    assert any(Path(filename).name in error for error in result["errors"])
    assert path.read_text() == "{broken"


@pytest.mark.parametrize("method, kind", [("list_servers", "servers"), ("list_nodes", "nodes"),
                                         ("list_groups", "groups"), ("list_aliases", "aliases"),
                                         ("list_templates", "templates"),
                                         ("list_schedules", "schedules"),
                                         ("list_alert_rules", "alerts")])
def test_verify_reports_storage_read_failure(tmp_path, monkeypatch, method, kind):
    manager = MigrationManager(tmp_path)
    monkeypatch.setattr(manager.storage, method, Mock(side_effect=OSError("database unavailable")))

    result = manager.verify()

    assert result["ok"] is False
    assert any(kind in error and "database unavailable" in error for error in result["errors"])
    assert len(result["checks"]) == 8


def test_migration_preserves_new_fields_and_marks_every_operational_type(tmp_path):
    schedule = {"command": "echo backup", "interval": 90, "enabled": False,
                "last_run": "2026-02-01", "server": "db", "created": "2026-01-01",
                "run_count": 17}
    template = {"command": "echo {app}", "description": "deploy app", "created": "2026-01-02"}
    sources = {
        ".schedule.json": {"nightly": schedule, "minimal": {"command": "echo default"}},
        ".templates.json": {"deploy": template, "legacy": "echo old"},
        ".node_keys.json": {"edge": {"host": "edge", "port": 1234, "key": "test-secret",
                                     "tls": True, "ca_file": "/certs/custom.pem"}},
    }
    for filename, data in sources.items():
        (tmp_path / filename).write_text(json.dumps(data))
    manager = MigrationManager(tmp_path)

    counts = manager.migrate_all()

    assert manager.errors == []
    assert counts["schedules"] == counts["templates"] == 2
    assert counts["nodes"] == 1
    store = StorageManager(tmp_path)
    schedules = {row["name"]: row for row in store.list_schedules()}
    assert {key: schedules["nightly"][key] for key in schedule if key != "interval"} == {
        key: value for key, value in schedule.items() if key != "interval"
    }
    assert schedules["nightly"]["interval_seconds"] == 90
    assert schedules["minimal"]["interval_seconds"] == 3600
    assert schedules["minimal"]["run_count"] == 0
    templates = {row["name"]: row for row in store.list_templates()}
    assert {key: templates["deploy"][key] for key in template} == template
    assert templates["legacy"]["command"] == "echo old"
    assert templates["legacy"]["description"] == ""
    assert templates["legacy"]["created"] is None
    node = store.get_node("edge")
    assert (node["auth_key"], node["tls"], node["ca_file"], node["port"]) == (
        "test-secret", 1, "/certs/custom.pem", 1234,
    )
    for kind in ("servers", "groups", "nodes", "alerts", "schedules", "templates", "aliases"):
        assert store.legacy_imported(kind) is True
    assert MigrationManager(tmp_path).verify()["ok"] is True
    for filename, data in sources.items():
        assert json.loads((tmp_path / filename).read_text()) == data


def test_verify_matching_existing_store_does_not_change_data_or_create_backups(tmp_path):
    path = tmp_path / ".aliases.json"
    path.write_text(json.dumps({"ll": "ls -l"}))
    manager = MigrationManager(tmp_path)
    manager.migrate_all()
    with manager.storage._get_connection() as conn:
        before = list(conn.iterdump())
    files_before = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
    source_before = path.read_bytes()

    result = manager.verify()

    assert result["ok"] is True
    assert result["errors"] == []
    assert len(result["checks"]) == 8
    assert all(check["match"] and check["detail"] == "match" for check in result["checks"])
    with manager.storage._get_connection() as conn:
        assert list(conn.iterdump()) == before
    assert path.read_bytes() == source_before
    assert {p.relative_to(tmp_path) for p in tmp_path.rglob("*")} == files_before
