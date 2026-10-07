"""Panic key rotation must survive a keyring reload.

`PanicManager` used to read and write `.node_keys.json` directly while SQLite
was the declared source of truth. Every `NodeKeyring` construction then rewrote
the JSON mirror from SQLite, so the emergency rotation silently reverted to the
pre-panic keys. These tests pin the rotation to storage.
"""

import json

import pytest

from cloudmesh.core.nodekeyring import NodeKeyring
from cloudmesh.core.panic import PanicManager
from cloudmesh.core.storage import StorageManager


class _FakeClient:
    """Stands in for NodeClient; records keys and can be told to fail."""

    instances = []
    fail_names = set()

    def __init__(self, host, port=9999, auth_key=None, tls=False, ca_file=None):
        """Record connection details and register this instance for inspection."""
        self.host = host
        self.port = port
        self.auth_key = auth_key
        self.rotated_to = None
        _FakeClient.instances.append(self)

    @classmethod
    def from_config(cls, info):
        """Build a fake client from a node config dict, like the real NodeClient."""
        return cls(
            info.get("host"),
            info.get("port", 9999),
            info.get("key"),
            info.get("tls", False),
            info.get("ca_file"),
        )

    def rotate_key(self, new_key):
        """Record the rotated key, or report failure for hosts marked to fail."""
        if self.host in _FakeClient.fail_names:
            return {"success": False, "message": "node refused"}
        self.rotated_to = new_key
        return {"success": True}


@pytest.fixture
def storage(tmp_path):
    """Return a fresh StorageManager backed by a temp directory."""
    return StorageManager(tmp_path)


@pytest.fixture
def keyring(tmp_path, storage):
    """Return a NodeKeyring pre-populated with a single node's key."""
    ring = NodeKeyring(storage=storage, base_dir=tmp_path)
    ring.save({"node-a": {"host": "10.0.0.1", "port": 9999, "key": "old-key-a"}})
    return ring


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch):
    """Replace NodeClient with _FakeClient and reset its state around each test."""
    _FakeClient.instances = []
    _FakeClient.fail_names = set()
    monkeypatch.setattr("cloudmesh.core.node_client.NodeClient", _FakeClient)
    yield
    _FakeClient.instances = []
    _FakeClient.fail_names = set()


def test_rotate_persists_new_keys_to_sqlite(tmp_path, storage, keyring):
    """The rotated key must be in storage, not only in the JSON mirror."""
    manager = PanicManager(base_dir=tmp_path, keyring=keyring)

    actions = manager.rotate_node_keys()

    assert _FakeClient.instances, "no node was contacted"
    rotated = _FakeClient.instances[0].rotated_to
    assert rotated and rotated != "old-key-a"
    assert any("confirmed remotely" in a for a in actions), actions

    rows = {n["name"]: n["auth_key"] for n in storage.list_nodes()}
    assert rows["node-a"] == rotated


def test_rotate_survives_a_fresh_keyring(tmp_path, storage, keyring):
    """The regression: a new keyring must not restore the pre-panic keys."""
    manager = PanicManager(base_dir=tmp_path, keyring=keyring)
    manager.rotate_node_keys()

    # Simulate the next CLI invocation building its own keyring.
    reloaded = NodeKeyring(storage=StorageManager(tmp_path), base_dir=tmp_path)

    assert reloaded.load()["node-a"]["key"] != "old-key-a"


def test_rotate_mirror_matches_storage(tmp_path, storage, keyring):
    """The JSON mirror and SQLite storage must agree on the rotated key."""
    manager = PanicManager(base_dir=tmp_path, keyring=keyring)
    manager.rotate_node_keys()

    mirror = json.loads((tmp_path / ".node_keys.json").read_text())
    rows = {n["name"]: n["auth_key"] for n in storage.list_nodes()}

    assert mirror["node-a"]["key"] == rows["node-a"]


def test_failed_rotation_is_queued_for_retry(tmp_path, storage, keyring):
    """A rotation an unreachable node refuses must be queued for later retry."""
    _FakeClient.fail_names = {"10.0.0.1"}
    manager = PanicManager(base_dir=tmp_path, keyring=keyring)

    actions = manager.rotate_node_keys()

    assert any("PENDING" in a for a in actions), actions
    pending = json.loads((tmp_path / ".panic_pending.json").read_text())
    assert "node-a" in pending
    assert pending["node-a"]["old_key"] == "old-key-a"


def test_retry_pending_commits_the_new_key(tmp_path, storage, keyring):
    """Retrying a pending rotation once the node is reachable must commit the key."""
    _FakeClient.fail_names = {"10.0.0.1"}
    manager = PanicManager(base_dir=tmp_path, keyring=keyring)
    manager.rotate_node_keys()

    _FakeClient.fail_names = set()  # node is reachable again
    actions = manager.retry_pending()

    assert any("Retry SUCCESS" in a for a in actions), actions
    rows = {n["name"]: n["auth_key"] for n in storage.list_nodes()}
    assert rows["node-a"] != "old-key-a"
    assert not (tmp_path / ".panic_pending.json").exists()


def test_execute_panic_reports_secret_invalidation(tmp_path, keyring):
    """Operators must be told stored passwords become unreadable."""
    manager = PanicManager(base_dir=tmp_path, keyring=keyring)

    actions = manager.dry_run()

    assert any("undecryptable" in desc for _, desc in actions), actions


@pytest.mark.skipif(__import__("os").name == "nt", reason="POSIX permissions only")
def test_secret_key_is_written_with_owner_only_permissions(tmp_path, keyring):
    """write_bytes() created the key 0644, downgrading StorageManager's 0600."""
    manager = PanicManager(base_dir=tmp_path, keyring=keyring)
    manager._write_secret_key(b"x" * 44)

    mode = (tmp_path / ".secret.key").stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"