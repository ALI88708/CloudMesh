"""Compatibility view of servers and nodes for older feature modules.

The SQLite-backed :class:`~cloudmesh.core.server.ServerManager` is the source
of truth, but several feature modules predate it and still read a flat
``data/cloudmesh.json``. That file is not created by the current manager, so
those commands reported "no servers configured" even after ``cm server add``.
This adapter returns the legacy dict shape, including the old ``key`` alias for
``key_path``, and still honours an existing JSON file during migration.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    from cloudmesh.core.storage import StorageManager, resolve_base_dir
except ImportError:  # pragma: no cover - source checkout without installed package
    from core.storage import StorageManager, resolve_base_dir


def _legacy_paths():
    base = resolve_base_dir()
    package = Path(__file__).resolve().parent.parent
    seen = set()
    for path in (base / "data" / "cloudmesh.json", package / "data" / "cloudmesh.json"):
        if path not in seen:
            seen.add(path)
            yield path


def _load_legacy():
    for path in _legacy_paths():
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and ("servers" in data or "nodes" in data):
            return data
    return {}


def _server_view(row):
    server = dict(row)
    server["key"] = server.get("key_path") or ""
    return server


def _node_view(row):
    node = dict(row)
    node["key"] = node.get("auth_key") or ""
    return node


def load_server_config():
    """Return the legacy ``{"servers": ..., "nodes": ...}`` shape.

    SQLite rows win over the JSON mirror so a newly added or removed server is
    visible immediately. A missing database, an unreadable file, or a corrupt
    row does not turn a read-only command into a traceback: the legacy file is
    returned on its own instead.
    """
    legacy = _load_legacy()
    merged = {
        "servers": dict(legacy.get("servers") or {}),
        "nodes": dict(legacy.get("nodes") or {}),
    }
    if isinstance(legacy.get("settings"), dict):
        merged["settings"] = legacy["settings"]

    try:
        storage = StorageManager()
        merged["servers"].update(
            {server["name"]: _server_view(server) for server in storage.list_servers()}
        )
        merged["nodes"].update(
            {node["name"]: _node_view(node) for node in storage.list_nodes()}
        )
    except Exception:
        # The JSON mirror is still useful when the database or key cannot be
        # opened, and a read-only install must not fail because SQLite is
        # unavailable.
        pass
    return merged


def get_server(name):
    return load_server_config()["servers"].get(name)


def get_node(name):
    return load_server_config()["nodes"].get(name)
