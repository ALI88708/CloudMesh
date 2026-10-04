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
