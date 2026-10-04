"""Pytest coverage for CloudMesh v3.2.0 SQLite backend review fixes."""

import json
import os
import sqlite3
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from cloudmesh.core.migrate import run_migration
from cloudmesh.core.storage import StorageManager


def _raw_secret(base: Path, table: str, column: str, name_col="name", name="srv1"):
    con = sqlite3.connect(base / "cloudmesh.db")
    try:
        row = con.execute(
            f"SELECT {column} FROM {table} WHERE {name_col} = ?", (name,)
        ).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def test_secrets_are_encrypted_not_plaintext(tmp_path):
    s = StorageManager(tmp_path)
    assert s.add_server("srv1", "h", "u", 22, None, "mysecret123")
    assert s.add_node("n1", "h", 9999, "nodekey456")
    raw_pw = _raw_secret(tmp_path, "servers", "password", name="srv1")
    raw_key = _raw_secret(tmp_path, "nodes", "auth_key", name="n1")
    assert raw_pw not in (None, "", "mysecret123")
    assert raw_key not in (None, "", "nodekey456")
    assert s.get_server("srv1")["password"] == "mysecret123"
    assert s.get_node("n1")["auth_key"] == "nodekey456"


def test_duplicate_returns_false_without_crash(tmp_path):
    s = StorageManager(tmp_path)
    assert s.add_server("srv1", "h", "u")
    assert s.add_server("srv1", "h", "u") is False
    assert s.add_node("n1", "h", 9999, "k")
    assert s.add_node("n1", "h", 9999, "k") is False


@pytest.mark.skipif(os.name == "nt", reason="POSIX perms only")
def test_db_file_is_private(tmp_path):
    s = StorageManager(tmp_path)
    s.add_server("srv1", "h", "u")
    mode = stat.S_IMODE(os.stat(tmp_path / "cloudmesh.db").st_mode)
    assert mode == 0o600
    key_mode = stat.S_IMODE(os.stat(tmp_path / ".secret.key").st_mode)
    assert key_mode == 0o600


def test_backup_uses_api_and_restore_roundtrip(tmp_path):
    s = StorageManager(tmp_path)
    s.add_server("srv1", "h", "u", 22, None, "pw1")
    s.set_setting("max_backups", 10)
    b1 = Path(s.backup_database())
    assert b1.exists()
    assert b1.read_bytes()[:16] == b"SQLite format 3\x00"
    # mutate then restore latest backup
    s.add_server("srv2", "h2", "u2")
    latest = sorted((tmp_path / "backups").glob("cloudmesh_backup_*.db"))[-1]
    assert s.restore_backup(str(latest)) is True
    assert s.get_server("srv2") is None
    assert s.get_server("srv1")["password"] == "pw1"


def test_backup_cleanup_respects_max_backups(tmp_path):
    s = StorageManager(tmp_path)
    s.set_setting("max_backups", 3)
    for _ in range(5):
        s.backup_database()
    assert len(list((tmp_path / "backups").glob("cloudmesh_backup_*.db"))) <= 3


def test_restore_rejects_path_traversal_and_non_db(tmp_path):
    s = StorageManager(tmp_path)
    assert s.restore_backup("../outside.db") is False
    evil = tmp_path / "notadb.db"
    evil.write_text("hello")
    assert s.restore_backup(str(evil)) is False


def test_restore_with_max_backups_one_keeps_source(tmp_path):
    s = StorageManager(tmp_path)
    s.set_setting("max_backups", 1)
    s.add_server("srv1", "h", "u", 22, None, "pw1")
    src = Path(s.backup_database())
    assert src.exists()
    # mutate, then restore the only backup in a later "second"
    s.add_server("srv2", "h2", "u2")
    assert s.restore_backup(str(src)) is True
    assert src.exists(), "restore source must survive retention cleanup"
    assert s.get_server("srv2") is None
    assert s.get_server("srv1")["password"] == "pw1"
    # live DB still has the full schema
    con = sqlite3.connect(tmp_path / "cloudmesh.db")
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    finally:
        con.close()
    assert "servers" in tables


def test_restore_refuses_empty_sqlite(tmp_path):
    s = StorageManager(tmp_path)
    s.add_server("srv1", "h", "u")
    empty = tmp_path / "backups" / "cloudmesh_backup_empty.db"
    c = sqlite3.connect(empty)
    c.execute("CREATE TABLE junk (id INTEGER)")
    c.commit()
    c.close()
    assert s.restore_backup(str(empty)) is False
    assert s.get_server("srv1") is not None


def _security_manager(tmp_path):
    try:
        from cloudmesh.core.security import SecurityManager
    except ImportError:
        from core.security import SecurityManager
    base = tmp_path / "sec"
    base.mkdir(exist_ok=True)
    return SecurityManager(base_dir=str(base))


def test_config_backups_are_encrypted(tmp_path):
    mgr = _security_manager(tmp_path)
    mgr.save_config({"servers": {"s": {"password": "topsecret"}}})
    mgr.save_config({"servers": {"s": {"password": "topsecret2"}}})
    backups = list(mgr.backups_dir.glob("config_backup_*"))
    assert backups, "expected at least one config backup"
    for b in backups:
        raw = b.read_bytes()
        assert b"topsecret" not in raw
        # new format: raw encrypted config bytes, decryptable
        assert json.loads(mgr.fernet.decrypt(raw).decode())["servers"]["s"]["password"].startswith("topsecret")


def test_config_restore_accepts_encrypted_and_legacy(tmp_path):
    mgr = _security_manager(tmp_path)
    mgr.save_config({"servers": {"a": {}}})
    # new format round-trip
    mgr.save_config({"servers": {"b": {}}})
    (mgr.backups_dir / "newfmt.json").write_bytes(mgr.config_path.read_bytes())
    mgr.restore_backup("newfmt.json")
    assert mgr.load_config() == {"servers": {"b": {}}}
    # legacy plaintext format still restores
    (mgr.backups_dir / "legacy.json").write_text(json.dumps({"servers": {"c": {}}}))
    mgr.restore_backup("legacy.json")
    assert mgr.load_config() == {"servers": {"c": {}}}


def test_dry_run_writes_nothing(tmp_path):
    (tmp_path / ".aliases.json").write_text(json.dumps({"a": "echo hi"}))
    (tmp_path / ".templates.json").write_text(
        json.dumps({"t1": {"command": "echo hi", "description": "d", "created": "now"}})
    )
    before = set(p.name for p in tmp_path.iterdir())
    r = run_migration(base_dir=tmp_path, dry_run=True)
    after = set(p.name for p in tmp_path.iterdir())
    assert r["dry_run"] is True
    assert r["success"] is True
    assert r["results"]["aliases"] == 1
    assert r["results"]["templates"] == 1
    assert after == before, f"dry-run created files: {after - before}"


def test_templates_dict_migrates_and_errors_fail_success(tmp_path):
    (tmp_path / ".templates.json").write_text(
        json.dumps({"t1": {"command": "echo hi", "description": "d", "created": "now"}})
    )
    r = run_migration(base_dir=tmp_path, dry_run=False)
    assert r["success"] is True
    assert r["results"]["templates"] == 1
    s = StorageManager(tmp_path)
    con = sqlite3.connect(tmp_path / "cloudmesh.db")
    try:
        row = con.execute("SELECT command FROM templates WHERE name='t1'").fetchone()
    finally:
        con.close()
    assert row[0] == "echo hi"

    # corrupt file must flip success to False and record errors
    (tmp_path / ".aliases.json").write_text("{not json")
    r2 = run_migration(base_dir=tmp_path, dry_run=False)
    assert r2["success"] is False
    assert any("aliases" in e.lower() for e in r2["errors"])


@pytest.mark.parametrize("created", [None, "2026-10-04T12:00:00"])
def test_schedule_upsert_preserves_identity_and_creation_time(tmp_path, created):
    store = StorageManager(tmp_path)
    original_created = "2026-01-01T00:00:00"
    store.upsert_schedule("nightly", "echo old", 60, created=original_created)
    original = store.list_schedules()[0]

    store.upsert_schedule(
        "nightly", "echo 'new'; -- literal SQL", 0, enabled=False,
        last_run="2026-10-03T12:00:00", server="db-1", created=created,
        run_count=42,
    )

    rows = StorageManager(tmp_path).list_schedules()
    assert len(rows) == 1
    assert rows[0] == {
        **original, "command": "echo 'new'; -- literal SQL", "interval_seconds": 0,
        "enabled": 0, "last_run": "2026-10-03T12:00:00", "server": "db-1",
        "created": created or original_created, "run_count": 42,
    }
    assert store.remove_schedule("missing") is False
    assert store.remove_schedule("nightly") is True
    assert StorageManager(tmp_path).list_schedules() == []


@pytest.mark.parametrize("created", [None, "2026-10-04T12:00:00"])
def test_template_upsert_preserves_identity_and_creation_time(tmp_path, created):
    store = StorageManager(tmp_path)
    store.upsert_template("deploy", "echo old", "old", "2026-01-01")
    original = store.list_templates()[0]

    store.upsert_template("deploy", "echo '{app}'", None, created)

    assert StorageManager(tmp_path).list_templates() == [{
        **original, "command": "echo '{app}'", "description": "",
        "created": created or "2026-01-01",
    }]
    assert store.remove_template("missing") is False
    assert store.remove_template("deploy") is True
    assert StorageManager(tmp_path).list_templates() == []


def test_alias_upsert_and_delete_treat_names_as_literal_data(tmp_path):
    store = StorageManager(tmp_path)
    name = "quote'; DROP TABLE aliases; --"
    store.upsert_alias(name, "echo old")
    store.upsert_alias("other", "echo untouched")
    store.upsert_alias(name, "echo 新しい")

    assert StorageManager(tmp_path).list_aliases() == {
        name: "echo 新しい", "other": "echo untouched",
    }
    assert store.remove_alias("missing") is False
    assert store.remove_alias(name) is True
    assert store.remove_alias(name) is False
    assert StorageManager(tmp_path).list_aliases() == {"other": "echo untouched"}


def test_alert_cooldowns_keep_rule_and_server_pairs_separate(tmp_path):
    store = StorageManager(tmp_path)
    assert store.list_alert_cooldowns() == {}
    store.set_alert_cooldown("cpu", "web", 100.25)
    store.set_alert_cooldown("cpu", "db", 200.5)
    store.set_alert_cooldown("ram", "web", 300.75)
    store.set_alert_cooldown("cpu", "web", 400.0)

    assert StorageManager(tmp_path).list_alert_cooldowns() == {
        "cpu|web": 400.0, "cpu|db": 200.5, "ram|web": 300.75,
    }


@pytest.mark.parametrize("value, expected", [("1", True), (1, True), (0, False),
                                            ("0", False), ("yes", False)])
def test_legacy_marker_normalizes_json_decoded_settings(tmp_path, value, expected):
    store = StorageManager(tmp_path)
    assert store.legacy_imported("nodes") is False
    store.set_setting("legacy_nodes_imported", value)
    assert StorageManager(tmp_path).legacy_imported("nodes") is expected
    assert store.legacy_imported("alerts") is False
    store.mark_legacy_imported("nodes")
    assert StorageManager(tmp_path).legacy_imported("nodes") is True


def test_schema_upgrade_preserves_legacy_rows_and_is_repeatable(tmp_path):
    # Build the three pre-3.3 tables independently of the current initializer.
    with sqlite3.connect(tmp_path / "cloudmesh.db") as conn:
        conn.executescript("""
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
                host TEXT NOT NULL, port INTEGER DEFAULT 9999,
                auth_key TEXT NOT NULL, status TEXT DEFAULT 'unknown',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
                command TEXT NOT NULL, interval_seconds INTEGER,
                enabled BOOLEAN DEFAULT 1, last_run TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
                command TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO nodes (name, host, auth_key) VALUES ('old', 'host', '');
            INSERT INTO schedules (name, command, interval_seconds)
                VALUES ('old', 'echo scheduled', 60);
            INSERT INTO templates (name, command) VALUES ('old', 'echo template');
        """)

    store = StorageManager(tmp_path)
    assert store.get_node("old")["tls"] == 0
    assert store.get_node("old")["ca_file"] is None
    schedule = store.list_schedules()[0]
    assert {key: schedule[key] for key in ("command", "server", "created", "run_count")} == {
        "command": "echo scheduled", "server": None, "created": None, "run_count": 0,
    }
    template = store.list_templates()[0]
    assert template["command"] == "echo template"
    assert template["description"] == ""
    assert template["created"] is None

    assert store.add_node("secure", "host", auth_key="test-secret", tls=True,
                          ca_file="/certs/ca.pem")
    store.upsert_schedule("old", "echo updated", 120, server="web", run_count=7)
    store.upsert_template("old", "echo updated", description="upgraded")
    reopened = StorageManager(tmp_path)
    assert reopened.get_node("secure")["tls"] == 1
    assert reopened.get_node("secure")["ca_file"] == "/certs/ca.pem"
    assert reopened.get_node("secure")["auth_key"] == "test-secret"
    assert reopened.list_schedules()[0]["run_count"] == 7
    assert reopened.list_templates()[0]["description"] == "upgraded"
    assert len(reopened.list_nodes()) == 2
