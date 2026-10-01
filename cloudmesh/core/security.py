import os
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


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
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.key_path.parent,
                prefix=f".{self.key_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(key)
                if os.name != "nt":
                    os.chmod(temp_path, 0o600)
            try:
                os.link(temp_path, self.key_path)
            except FileExistsError:
                return self.key_path.read_bytes()
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
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
        self._write_encrypted_config(encrypted)

    def _write_encrypted_config(self, encrypted: bytes):
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.config_path.parent,
                prefix=f".{self.config_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(encrypted)
            os.replace(temp_path, self.config_path)
            temp_path = None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
        try:
            if os.name != "nt":
                os.chmod(self.config_path, 0o600)
        except Exception as e:
            logger.warning("Failed to set config permissions: %s", e)

    def load_config(self) -> dict:
        if not self.config_path.exists():
            return {"servers": {}, "settings": {"monitor_interval": 5, "max_backups": 10}}
        encrypted = self.config_path.read_bytes()
        try:
            decrypted = self.fernet.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error("Failed to load config: %s", e)
            return {"servers": {}, "settings": {"monitor_interval": 5, "max_backups": 10}}

    def _backup_config(self):
        if not self.config_path.exists():
            return
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        try:
            original = self.config_path.read_bytes()
        except OSError as e:
            logger.error("Backup read failed: %s", e)
            return
        try:
            backup_data = self.fernet.decrypt(original)
        except Exception as e:
            logger.warning("Backup decrypt failed, copying raw: %s", e)
            backup_data = original

        suffix = 0
        while True:
            suffix_part = f"_{suffix}" if suffix else ""
            backup_path = self.backups_dir / f"config_backup_{timestamp}{suffix_part}.json"
            try:
                backup_fd = os.open(
                    backup_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o666,
                )
                break
            except FileExistsError:
                suffix += 1
            except OSError as e:
                logger.error("Backup reservation failed: %s", e)
                return

        try:
            with os.fdopen(backup_fd, "wb") as backup_file:
                backup_file.write(backup_data)
        except Exception as e:
            logger.error("Backup write failed: %s", e)
            try:
                backup_path.unlink()
            except FileNotFoundError:
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
        if not backup_path.is_absolute():
            backup_path = self.backups_dir / backup_path
        backups_dir = self.backups_dir.resolve()
        try:
            backup_path = backup_path.resolve()
        except OSError as e:
            logger.error("Invalid backup path: %s", e)
            raise ValueError("Invalid backup path")
        if backups_dir not in backup_path.parents:
            logger.error("Path traversal blocked: %s", backup_file)
            raise ValueError("Restore path must be inside the backups directory")
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_file}")
        self._backup_config()
        data = backup_path.read_bytes()
        try:
            json.loads(data.decode())
            encrypted = self.fernet.encrypt(data)
            self._write_encrypted_config(encrypted)
        except json.JSONDecodeError:
            raise ValueError("Backup file is not valid JSON")

    def list_backups(self):
        return sorted(self.backups_dir.glob("config_backup_*"), reverse=True)
