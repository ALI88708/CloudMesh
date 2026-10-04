"""Node keyring with SQLite as the source of truth.

Keyring shape matches the legacy ``.node_keys.json`` file::

    {name: {"host": ..., "port": ..., "key": ...,
            ["tls": True], ["ca_file": ...]}}

The JSON file is kept as a compatible mirror. A persistent settings marker
makes the one-time legacy import run exactly once: an empty nodes table is
a valid state (e.g. after a restore) and must not trigger a re-import.
"""

import json
import logging
from pathlib import Path
from typing import Dict

try:
    from cloudmesh.core.storage import StorageManager
except ImportError:  # `cd cloudmesh && pytest tests` without installed package
    from core.storage import StorageManager

logger = logging.getLogger(__name__)


class NodeKeyring:
    def __init__(self, storage=None, json_path=None, base_dir=None):
        """Open a keyring and attempt a marker-guarded JSON import.

        Create storage under base_dir if omitted. json_path defaults to
        .node_keys.json under base_dir, or the supplied storage's base directory.
        Storage initialization errors propagate.
        """
        if storage is None:
            storage = StorageManager(base_dir)
        self.storage = storage
        if json_path is None:
            base = Path(base_dir) if base_dir is not None else storage.base_dir
            json_path = Path(base) / ".node_keys.json"
        self.json_path = Path(json_path)
        self._ensure_imported()

    # -- internal ------------------------------------------------------
    @staticmethod
    def _to_legacy(row: dict) -> dict:
        """Return host, port, and key fields plus truthy TLS and CA settings."""
        entry = {
            "host": row.get("host"),
            "port": row.get("port", 9999),
            "key": row.get("auth_key", ""),
        }
        if row.get("tls"):
            entry["tls"] = True
        if row.get("ca_file"):
            entry["ca_file"] = row.get("ca_file")
        return entry

    def _read_json(self) -> Dict:
        """Return the JSON keyring, or {} for missing, unreadable, or non-object data."""
        if not self.json_path.exists():
            return {}
        try:
            data = json.loads(self.json_path.read_text())
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_json(self, keys: Dict) -> None:
        """Write a private JSON mirror, creating its parent directory if needed.

        Serialization and filesystem errors are suppressed; failure to import
        the writer propagates.
        """
        try:
            from cloudmesh.core.node_client import save_private_json
        except ImportError:
            from core.node_client import save_private_json
        try:
            self.json_path.parent.mkdir(parents=True, exist_ok=True)
            save_private_json(self.json_path, keys)
        except Exception as e:
            logger.warning("Failed to write node keys mirror: %s", e)

    def _ensure_imported(self) -> None:
        """Import legacy node dictionaries unless marked, then refresh JSON.

        Skip invalid entries and storage failures; attempt to mark the import
        even if some nodes failed.
        """
        try:
            if self.storage.legacy_imported("nodes"):
                self._push_mirror()
                return
        except Exception:
            return
        try:
            raw = self.json_path.read_text() if self.json_path.exists() else "{}"
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("node keys file is not an object")
        except Exception as e:
            logger.error("NodeKeyring cannot read legacy keys; marker left unset: %s", e)
            return
        ok = True
        for name, info in list(data.items()):
            if not isinstance(info, dict):
                continue
            try:
                if not self.storage.add_node(
                    name=name,
                    host=info.get("host"),
                    port=info.get("port", 9999),
                    auth_key=info.get("key", ""),
                    tls=bool(info.get("tls", False)),
                    ca_file=info.get("ca_file"),
                ):
                    raise RuntimeError("storage rejected node")
            except Exception:
                ok = False
                continue
        if not ok:
            logger.warning("NodeKeyring import incomplete; marker left unset")
            return
        try:
            self.storage.mark_legacy_imported("nodes")
        except Exception:
            pass
        self._push_mirror()

    def _push_mirror(self) -> None:
        """Refresh changed JSON from stored nodes; leave it intact on read failure."""
        try:
            rows = {n["name"]: self._to_legacy(n) for n in self.storage.list_nodes()}
        except Exception:
            return
        if rows != self._read_json():
            self._write_json(rows)

    # -- public dict-style API ------------------------------------------
    def load(self) -> Dict:
        """Return nodes by name with host, port, key, and optional TLS settings.

        Use SQLite rows when nonempty; otherwise fall back to the JSON mirror,
        including on storage failure. Missing or unreadable JSON yields {}.
        """
        try:
            rows = self.storage.list_nodes()
            if rows:
                return {n["name"]: self._to_legacy(n) for n in rows}
        except Exception as e:
            logger.warning("NodeKeyring falling back to JSON mirror: %s", e)
        return self._read_json()

    def save(self, keys: Dict) -> None:
        """Reconcile SQLite with a legacy keyring and refresh JSON from storage.

        Accept a name-to-node mapping; None means empty. Skip non-dictionary
        entries and attempt to remove stored names absent from keys. Storage
        failures are suppressed, so updates may be partial and the mirror
        reflects stored rows, not necessarily keys. Invalid mapping conversion
        raises TypeError or ValueError.
        """
        keys = dict(keys or {})
        try:
            current = {n["name"] for n in self.storage.list_nodes()}
        except Exception:
            current = set()
        for name, info in keys.items():
            if not isinstance(info, dict):
                continue
            try:
                if not self.storage.upsert_node(
                    name=name,
                    host=info.get("host"),
                    port=info.get("port", 9999),
                    auth_key=info.get("key", ""),
                    tls=bool(info.get("tls", False)),
                    ca_file=info.get("ca_file"),
                ):
                    raise RuntimeError(f"upsert failed for node {name}")
            except Exception as e:
                logger.warning("Failed to save node %s: %s", name, e)
        for stale in current - set(keys):
            try:
                self.storage.remove_node(stale)
            except Exception:
                pass
        self._push_mirror()
