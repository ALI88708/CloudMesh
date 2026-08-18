import json
import secrets
import shutil
from pathlib import Path
from datetime import datetime

from cryptography.fernet import Fernet


class PanicManager:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path(__file__).parent.parent)
        self.secret_key_file = self.base_dir / ".secret.key"
        self.node_keys_file = self.base_dir / ".node_keys.json"
        self.panic_log_file = self.base_dir / ".panic_log.json"

    def _log_panic(self, actions):
        entries = []
        if self.panic_log_file.exists():
            try:
                entries = json.loads(self.panic_log_file.read_text())
            except Exception:
                entries = []
        entry = {
            "timestamp": datetime.now().isoformat(),
            "actions": actions,
        }
        entries.append(entry)
        entries = entries[-100:]
        self.panic_log_file.write_text(json.dumps(entries, indent=2))

    def dry_run(self):
        actions = []
        if self.secret_key_file.exists():
            actions.append(("rotate_secret_key", "Will generate new Fernet encryption key"))
        else:
            actions.append(("rotate_secret_key", "No key file found — will create new one"))

        if self.node_keys_file.exists():
            try:
                nodes = json.loads(self.node_keys_file.read_text())
                for name in nodes:
                    actions.append(("rotate_node_key", f"Will rotate auth key for node '{name}'"))
                actions.append(("backup_node_keys", f"Will backup .node_keys.json"))
            except Exception:
                actions.append(("rotate_node_keys", "Will regenerate .node_keys.json"))
        else:
            actions.append(("rotate_node_keys", "No .node_keys.json found — nothing to rotate"))

        actions.append(("log_panic", "Will record panic event in .panic_log.json"))
        return actions

    def execute_panic(self):
        actions = []

        if self.secret_key_file.exists():
            shutil.copy2(self.secret_key_file, self.secret_key_file.with_suffix(".key.bak"))
            new_key = Fernet.generate_key()
            self.secret_key_file.write_bytes(new_key)
            actions.append("Rotated .secret.key (backup saved as .secret.key.bak)")
        else:
            new_key = Fernet.generate_key()
            self.secret_key_file.write_bytes(new_key)
            actions.append("Created new .secret.key (none existed before)")

        if self.node_keys_file.exists():
            try:
                nodes = json.loads(self.node_keys_file.read_text())
                shutil.copy2(self.node_keys_file, self.node_keys_file.with_suffix(".json.bak"))
                for name in nodes:
                    new_auth = secrets.token_hex(32)
                    nodes[name]["key"] = new_auth
                self.node_keys_file.write_text(json.dumps(nodes, indent=2))
                actions.append(f"Rotated auth keys for {len(nodes)} node(s) (backup saved as .node_keys.json.bak)")
            except Exception as e:
                actions.append(f"Error rotating node keys: {e}")
        else:
            actions.append("No .node_keys.json found — skipped node key rotation")

        self._log_panic(actions)
        actions.append(f"Panic event logged at {datetime.now().isoformat()}")

        return actions
