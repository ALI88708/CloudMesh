import json
from datetime import datetime
from pathlib import Path


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
        entry = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "args": args,
        }
        self._entries.append(entry)
        self._save()

    def get_recent(self, limit=50):
        return self._entries[-limit:]

    def search(self, keyword):
        return [e for e in self._entries if keyword.lower() in e.get("command","").lower() or keyword.lower() in e.get("args","").lower()]

    def clear(self):
        self._entries = []
        self._save()
