import json
from pathlib import Path

try:
    from cloudmesh.core.storage import StorageManager
except ImportError:  # `cd cloudmesh && pytest tests` without installed package
    from core.storage import StorageManager


class GroupsManager:
    """Manage groups with SQLite as the source of truth.

    The legacy JSON config section is kept as a compatible mirror, and any
    legacy JSON groups are imported once into SQLite on init.
    """

    def __init__(self, security_manager, storage=None):
        self.security = security_manager
        self.config = self.security.load_config()
        if "groups" not in self.config:
            self.config["groups"] = {}
        if storage is None:
            storage = StorageManager(self.security.base_dir)
        self.storage = storage
        self._import_legacy_groups()

    def _import_legacy_groups(self):
        try:
            if self.storage.list_groups():
                return
        except Exception:
            return
        for group_name, devices in list(self.config.get("groups", {}).items()):
            if not isinstance(devices, list):
                continue
            try:
                self.storage.create_group(group_name)
            except Exception:
                pass
            for device in devices:
                try:
                    self.storage.add_to_group(group_name, device, "server")
                except Exception:
                    continue

    def _save(self):
        self.security.save_config(self.config)

    def _mirror(self):
        try:
            self.config["groups"] = self.storage.list_groups()
        except Exception:
            pass

    def create_group(self, name):
        try:
            existing = self.storage.list_groups()
        except Exception:
            existing = {}
        if name in existing or name in self.config["groups"]:
            raise ValueError(f"Group '{name}' already exists")
        try:
            if not self.storage.create_group(name):
                raise ValueError(f"Group '{name}' already exists")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Group '{name}' could not be created: {e}")
        self._mirror()
        self._save()

    def delete_group(self, name):
        try:
            found = self.storage.delete_group(name)
        except Exception:
            found = False
        if name not in self.config["groups"] and not found:
            raise ValueError(f"Group '{name}' not found")
        self._mirror()
        self._save()

    def add_to_group(self, group_name, device_name):
        try:
            self.storage.create_group(group_name)
        except Exception:
            pass
        try:
            self.storage.add_to_group(group_name, device_name, "server")
        except Exception:
            pass
        self._mirror()
        self._save()

    def remove_from_group(self, group_name, device_name):
        try:
            self.storage.remove_from_group(group_name, device_name)
        except Exception:
            pass
        self._mirror()
        self._save()

    def get_group_devices(self, group_name):
        try:
            devices = self.storage.get_group_devices(group_name)
            if devices:
                return devices
        except Exception:
            pass
        return self.config["groups"].get(group_name, [])

    def list_groups(self):
        try:
            groups = self.storage.list_groups()
            if groups:
                return dict(groups)
        except Exception:
            pass
        return dict(self.config["groups"])

    def rename_group(self, old_name, new_name):
        devices = self.get_group_devices(old_name)
        if not devices and old_name not in self.list_groups():
            raise ValueError(f"Group '{old_name}' not found")
        self.create_group(new_name)
        for device in devices:
            self.add_to_group(new_name, device)
        self.delete_group(old_name)

    def rename_group(self, old_name, new_name):
        if old_name not in self.config["groups"]:
            raise ValueError(f"Group '{old_name}' not found")
        self.config["groups"][new_name] = self.config["groups"].pop(old_name)
        self._save()
