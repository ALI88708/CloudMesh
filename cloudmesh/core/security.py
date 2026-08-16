import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from cryptography.fernet import Fernet


class SecurityManager:
    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        self.base_dir = Path(base_dir)
        self.config_path = self.base_dir / "config.json"
        self.key_path = self.base_dir / ".secret.key"
        self.backups_dir = self.base_dir / "backups"
        self.backups_dir.mkdir(exist_ok=True)
        self._fernet = None

    def _get_or_create_key(self):
        if self.key_path.exists():
            return self.key_path.read_bytes()
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        try:
            if os.name != "nt":
                os.chmod(self.key_path, 0o600)
        except Exception:
            pass
        return key

    @property
    def fernet(self):
        if self._fernet is None:
            self._fernet = Fernet(self._get_or_create_key())
        return self._fernet

    def save_config(self, config: dict):
        self._backup_config()
        data = json.dumps(config, indent=2).encode()
        encrypted = self.fernet.encrypt(data)
        self.config_path.write_bytes(encrypted)
        try:
            if os.name != "nt":
                os.chmod(self.config_path, 0o600)
        except Exception:
            pass

    def load_config(self) -> dict:
        if not self.config_path.exists():
            return {"servers": {}, "settings": {"monitor_interval": 5, "max_backups": 10}}
        encrypted = self.config_path.read_bytes()
        try:
            decrypted = self.fernet.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception:
            return {"servers": {}, "settings": {"monitor_interval": 5, "max_backups": 10}}

    def _backup_config(self):
        if not self.config_path.exists():
            return
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = f"config_backup_{timestamp}.json"
        backup_path = self.backups_dir / backup_name
        try:
            decrypted = self.fernet.decrypt(self.config_path.read_bytes())
            backup_path.write_bytes(decrypted)
        except Exception:
            try:
                shutil.copy2(self.config_path, backup_path)
            except Exception:
                pass
        self._cleanup_old_backups()

    def _cleanup_old_backups(self):
        config = self.load_config()
        max_backups = config.get("settings", {}).get("max_backups", 10)
        backups = sorted(self.backups_dir.glob("config_backup_*"))
        while len(backups) > max_backups:
            oldest = backups.pop(0)
            oldest.unlink()

    def restore_backup(self, backup_file: str):
        backup_path = Path(backup_file)
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_file}")
        self._backup_config()
        data = backup_path.read_bytes()
        try:
            json.loads(data.decode())
            encrypted = self.fernet.encrypt(data)
            self.config_path.write_bytes(encrypted)
        except json.JSONDecodeError:
            raise ValueError("Backup file is not valid JSON")

    def list_backups(self):
        return sorted(self.backups_dir.glob("config_backup_*"), reverse=True)
