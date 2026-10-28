"""Maintenance state for nodes.

Drain state lives beside the node keyring rather than inside it: the
keyring's SQLite source of truth has a fixed shape (host/port/key/tls/ca)
and rebuilds unknown fields away on load, so a flag smuggled through it
would vanish at the next read. It is also not a secret -- losing this file
means the scheduler forgets a maintenance window, not that a key is gone.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

try:
    from cloudmesh.core.storage import resolve_base_dir
except ImportError:  # `cd cloudmesh && pytest tests` without installed package
    from core.storage import resolve_base_dir

DRAIN_FILENAME = ".node_drain.json"


class DrainRegistry:
    def __init__(self, base_dir=None):
        base = Path(base_dir) if base_dir is not None else resolve_base_dir()
        self.path = base / DRAIN_FILENAME

    def load(self):
        """Return {name: {"reason": ..., "at": ...}}; {} when unreadable."""
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {name: entry for name, entry in data.items() if isinstance(entry, dict)}

    def names(self):
        return set(self.load())

    def is_drained(self, name):
        return name in self.load()

    def drain(self, name, reason=None):
        data = self.load()
        data[name] = {
            "reason": reason,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self._write(data)
        return data[name]

    def undrain(self, name):
        data = self.load()
        if name not in data:
            return False
        del data[name]
        self._write(data)
        return True

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f"{self.path.name}.tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
        )
        os.replace(temporary, self.path)
