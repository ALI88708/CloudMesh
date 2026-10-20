import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from .paths import base_dir as default_base_dir


GENESIS_HASH = "0" * 64
CHECKPOINT_VERSION = 1
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def _compute_hash(prev_hash, timestamp, command, args=""):
    raw = f"{prev_hash}{timestamp}{command}{args}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload) -> None:
    """Write JSON atomically, with owner-only permissions where supported."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f"{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


class CommandLog:
    def __init__(self, base_dir=None, max_entries=500):
        if base_dir is None:
            base_dir = default_base_dir()
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.base_dir / "command_log.json"
        self.checkpoint_file = self.base_dir / "command_log.checkpoint.json"
        self.max_entries = max_entries
        self._entries = []
        self._checkpoint = None
        self._checkpoint_error = None
        self._load()

    def _load(self):
        if self.log_file.exists():
            try:
                entries = json.loads(self.log_file.read_text())
                if isinstance(entries, list):
                    self._entries = entries
            except Exception:
                self._entries = []

        if self.checkpoint_file.exists():
            try:
                data = json.loads(self.checkpoint_file.read_text())
                anchor = data.get("anchor_hash") if isinstance(data, dict) else None
                dropped = data.get("dropped") if isinstance(data, dict) else None
                version = data.get("version") if isinstance(data, dict) else None
                if (
                    version != CHECKPOINT_VERSION
                    or not isinstance(anchor, str)
                    or not _HEX64.fullmatch(anchor)
                    or not isinstance(dropped, int)
                    or isinstance(dropped, bool)
                    or dropped < 0
                ):
                    raise ValueError("invalid checkpoint fields")
                self._checkpoint = {
                    "anchor_hash": anchor.lower(),
                    "dropped": dropped,
                    "version": CHECKPOINT_VERSION,
                }
            except Exception as exc:
                self._checkpoint = None
                self._checkpoint_error = str(exc) or "unreadable checkpoint"

    def _save(self):
        overflow = len(self._entries) - self.max_entries
        if overflow <= 0:
            _write_json(self.log_file, self._entries)
            return

        dropped_entries = self._entries[:overflow]
        self._entries = self._entries[overflow:]
        anchor = dropped_entries[-1].get("entry_hash", GENESIS_HASH)
        previous_dropped = self._checkpoint["dropped"] if self._checkpoint else 0
        checkpoint = {
            "anchor_hash": str(anchor).lower(),
            "dropped": previous_dropped + overflow,
            "version": CHECKPOINT_VERSION,
        }

        _write_json(self.log_file, self._entries)
        _write_json(self.checkpoint_file, checkpoint)
        self._checkpoint = checkpoint
        self._checkpoint_error = None

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
        if self._checkpoint_error:
            return {
                "valid": False,
                "total": len(self._entries),
                "message": f"Checkpoint BROKEN — {self._checkpoint_error}.",
            }
        if not self._entries:
            return {"valid": True, "entries": 0, "message": "Empty log — nothing to verify."}

        legacy_truncated = False
        if self._checkpoint is not None:
            anchor = self._checkpoint["anchor_hash"]
        else:
            first_prev = self._entries[0].get("prev_hash", GENESIS_HASH)
            if first_prev != GENESIS_HASH:
                anchor = first_prev
                legacy_truncated = True
            else:
                anchor = GENESIS_HASH

        broken_at = None
        for i, entry in enumerate(self._entries):
            prev_expected = anchor if i == 0 else self._entries[i - 1].get("entry_hash", GENESIS_HASH)
            prev_actual = entry.get("prev_hash", GENESIS_HASH)

            if prev_actual != prev_expected:
                broken_at = i
                break

            if legacy_truncated and i == 0:
                continue

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

        result = {
            "valid": True,
            "total": len(self._entries),
            "message": f"Chain intact — all {len(self._entries)} entries verified.",
        }
        if legacy_truncated:
            result["legacy_truncated"] = True
        if self._checkpoint is not None:
            result["dropped"] = self._checkpoint["dropped"]
        return result

    def clear(self):
        self._entries = []
        self._checkpoint = None
        self._checkpoint_error = None
        try:
            self.checkpoint_file.unlink()
        except FileNotFoundError:
            pass
        self._save()
