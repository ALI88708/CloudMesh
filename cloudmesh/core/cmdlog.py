import json
import hashlib
from datetime import datetime
from pathlib import Path


GENESIS_HASH = "0" * 64


def _compute_hash(prev_hash, timestamp, command, args=""):
    raw = f"{prev_hash}{timestamp}{command}{args}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CommandLog:
    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        self.base_dir = Path(base_dir)
        self.log_file = self.base_dir / "command_log.json"
        self._entries = []
        self._load()

    def _load(self):
        if self.log_file.exists():
            try:
                self._entries = json.loads(self.log_file.read_text())
            except Exception:
                self._entries = []

    def _save(self):
        self._entries = self._entries[-500:]
        self.log_file.write_text(json.dumps(self._entries, indent=2))

    def log(self, command, args=""):
        timestamp = datetime.now().isoformat()
        prev_hash = self._entries[-1].get("entry_hash", GENESIS_HASH) if self._entries else GENESIS_HASH
        entry_hash = _compute_hash(prev_hash, timestamp, command, args)
        entry = {
            "timestamp": timestamp,
            "command": command,
            "args": args,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
            "version": 2,
        }
        self._entries.append(entry)
        self._save()

    def get_recent(self, limit=50):
        return self._entries[-limit:]

    def search(self, keyword):
        return [e for e in self._entries if keyword.lower() in e.get("command", "").lower() or keyword.lower() in e.get("args", "").lower()]

    def verify(self):
        if not self._entries:
            return {"valid": True, "entries": 0, "message": "Empty log — nothing to verify."}

        broken_at = None
        for i, entry in enumerate(self._entries):
            prev_expected = self._entries[i - 1].get("entry_hash", GENESIS_HASH) if i > 0 else GENESIS_HASH
            prev_actual = entry.get("prev_hash", GENESIS_HASH)

            if prev_actual != prev_expected:
                broken_at = i
                break

            if entry.get("version") == 2 and "entry_hash" in entry:
                computed = _compute_hash(
                    prev_actual,
                    entry["timestamp"],
                    entry.get("command", ""),
                    entry.get("args", ""),
                )
                if computed != entry.get("entry_hash"):
                    broken_at = i
                    break

        if broken_at is not None:
            return {
                "valid": False,
                "broken_at": broken_at,
                "total": len(self._entries),
                "message": f"Chain BROKEN at entry #{broken_at} — possible tampering detected.",
                "entry": self._entries[broken_at],
            }

        return {
            "valid": True,
            "total": len(self._entries),
            "message": f"Chain intact — all {len(self._entries)} entries verified.",
        }

    def clear(self):
        self._entries = []
        self._save()
