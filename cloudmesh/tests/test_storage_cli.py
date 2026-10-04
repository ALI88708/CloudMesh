"""Unit tests for the CLI storage wiring introduced in PR #16."""

import argparse
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from rich.console import Console

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

import cloudmesh.main as main
from cloudmesh.core import features, migrate, security, storage


@pytest.mark.parametrize("ok", [True, False])
def test_migrate_verify_reports_status_and_exit_code(tmp_path, monkeypatch, capsys, ok):
    manager = Mock()
    manager.verify.return_value = {
        "ok": ok, "checks": [{"type": "nodes", "json": ["edge"],
                                "sqlite": ["edge"] if ok else [], "match": ok}],
        "errors": [] if ok else ["database unavailable"],
    }
    factory = Mock(return_value=manager)
    run = Mock(side_effect=AssertionError("verify must not run migration"))
    monkeypatch.setattr(migrate, "MigrationManager", factory)
    monkeypatch.setattr(migrate, "run_migration", run)
    monkeypatch.setattr(main, "console", Console(width=120, color_system=None))
    args = argparse.Namespace(base_dir=str(tmp_path), verify=True, dry_run=False)

    if ok:
        main.cmd_migrate(args)
    else:
        with pytest.raises(SystemExit) as exc:
            main.cmd_migrate(args)
        assert exc.value.code == 1

    factory.assert_called_once_with(tmp_path)
    manager.verify.assert_called_once_with()
    run.assert_not_called()
    output = capsys.readouterr().out
    assert "nodes" in output
    assert ("Verify: OK" if ok else "Verify: FAILED") in output
    if not ok:
        assert "MISMATCH" in output
        assert "database unavailable" in output


def test_migrate_parser_forwards_verify_and_base_directory(tmp_path, monkeypatch):
    handler = Mock()
    monkeypatch.setattr(main, "cmd_migrate", handler)
    monkeypatch.setattr(sys, "argv", ["cm", "migrate", "--verify", "--base-dir", str(tmp_path)])

    main.main()

    handler.assert_called_once()
    args = handler.call_args.args[0]
    assert args.verify is True
    assert args.base_dir == str(tmp_path)
    assert args.dry_run is False


def test_node_key_helpers_use_redirected_file_parent_for_storage(tmp_path, monkeypatch):
    path = tmp_path / "isolated" / ".node_keys.json"
    monkeypatch.setattr(main, "NODE_KEYS_FILE", path)
    keys = {"edge": {"host": "edge", "port": 9999, "key": "test-secret",
                     "tls": True, "ca_file": "/certs/ca.pem"}}

    main._save_node_keys(keys)

    assert main._load_node_keys() == keys
    assert (path.parent / "cloudmesh.db").exists()
    assert json.loads(path.read_text()) == keys
    assert storage.StorageManager(path.parent).get_node("edge")["tls"] == 1
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("contents, expected", [(None, {}), ("{broken", {}),
                                               ('{"edge": {"host": "edge"}}',
                                                {"edge": {"host": "edge"}})])
def test_node_key_load_falls_back_when_keyring_cannot_start(tmp_path, monkeypatch, contents, expected):
    path = tmp_path / ".node_keys.json"
    if contents is not None:
        path.write_text(contents)
    monkeypatch.setattr(main, "NODE_KEYS_FILE", path)
    monkeypatch.setattr(main, "_get_node_keyring", Mock(side_effect=OSError("offline")))
    assert main._load_node_keys() == expected


def test_node_key_save_fallback_writes_private_json(tmp_path, monkeypatch):
    path = tmp_path / ".node_keys.json"
    monkeypatch.setattr(main, "NODE_KEYS_FILE", path)
    monkeypatch.setattr(main, "_get_node_keyring", Mock(side_effect=OSError("offline")))
    keys = {"edge": {"host": "edge", "key": "test-secret"}}
    main._save_node_keys(keys)
    assert json.loads(path.read_text()) == keys
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("package_version", ["9.8.7", None])
def test_get_version_uses_metadata_with_source_checkout_fallback(monkeypatch, package_version):
    lookup = Mock(return_value=package_version)
    if package_version is None:
        lookup.side_effect = importlib.metadata.PackageNotFoundError("cloudmesh")
    monkeypatch.setattr(importlib.metadata, "version", lookup)

    result = features.get_version()

    assert result == {"version": package_version or "3.3.0", "platform": sys.platform,
                      "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"}
    lookup.assert_called_once_with("cloudmesh")


@pytest.mark.parametrize("healthy", [True, False])
def test_doctor_reports_storage_markers_mirrors_permissions_and_backups(tmp_path, monkeypatch, capsys, healthy):
    store = storage.StorageManager(tmp_path)
    if healthy:
        for kind in ("servers", "groups", "nodes", "alerts", "schedules", "templates", "aliases"):
            store.mark_legacy_imported(kind)
    store.backup_database()
    if not healthy and os.name != "nt":
        store.db_path.chmod(0o644)
        store.key_path.chmod(0o644)
    # Use the already initialized store so initialization cannot repair the modes.
    monkeypatch.setattr(storage, "StorageManager", Mock(return_value=store))
    monkeypatch.setattr(main, "__file__", str(tmp_path / "main.py"))
    monkeypatch.setattr(main, "console", Console(width=160, color_system=None))
    config = {"servers": {} if healthy else {"stale": {}}}
    monkeypatch.setattr(security, "SecurityManager", Mock(return_value=Mock(load_config=Mock(return_value=config))))
    monkeypatch.setattr(main, "_load_node_keys", Mock(return_value={} if healthy else {"stale": {}}))

    main.cmd_doctor(argparse.Namespace())

    lines = capsys.readouterr().out.splitlines()
    expected_status = "PASS" if healthy else "FAIL"
    labels = ["Storage: legacy import", "Storage: servers mirror", "Storage: nodes mirror"]
    if os.name != "nt":
        labels += ["Storage: database perms", "Storage: key perms"]
    for label in labels:
        assert expected_status in next(line for line in lines if label in line)
    assert ("7/7" if healthy else "0/7") in next(line for line in lines if "Storage: legacy import" in line)
    backup_line = next(line for line in lines if "Storage: backups" in line)
    assert "PASS" in backup_line
    assert "1 sqlite backup(s)" in backup_line


def test_doctor_reports_storage_initialization_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(main, "__file__", str(tmp_path / "main.py"))
    monkeypatch.setattr(main, "console", Console(width=120, color_system=None))
    monkeypatch.setattr(storage, "StorageManager", Mock(side_effect=OSError("database unavailable")))

    main.cmd_doctor(argparse.Namespace())

    line = next(line for line in capsys.readouterr().out.splitlines() if "Storage backend" in line)
    assert "FAIL" in line
    assert "database unavailable" in line
