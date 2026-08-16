import json
from pathlib import Path


class GroupsManager:
    def __init__(self, security_manager):
        self.security = security_manager
        self.config = self.security.load_config()
        if "groups" not in self.config:
            self.config["groups"] = {}

    def _save(self):
        self.security.save_config(self.config)

    def create_group(self, name):
        if name in self.config["groups"]:
            raise ValueError(f"Group '{name}' already exists")
        self.config["groups"][name] = []
        self._save()

    def delete_group(self, name):
        if name not in self.config["groups"]:
            raise ValueError(f"Group '{name}' not found")
        del self.config["groups"][name]
        self._save()

    def add_to_group(self, group_name, device_name):
        if group_name not in self.config["groups"]:
            self.config["groups"][group_name] = []
        if device_name not in self.config["groups"][group_name]:
            self.config["groups"][group_name].append(device_name)
            self._save()

    def remove_from_group(self, group_name, device_name):
        if group_name not in self.config["groups"]:
            return
        if device_name in self.config["groups"][group_name]:
            self.config["groups"][group_name].remove(device_name)
            self._save()

    def get_group_devices(self, group_name):
        return self.config["groups"].get(group_name, [])

    def list_groups(self):
        return dict(self.config["groups"])

    def rename_group(self, old_name, new_name):
        if old_name not in self.config["groups"]:
            raise ValueError(f"Group '{old_name}' not found")
        self.config["groups"][new_name] = self.config["groups"].pop(old_name)
        self._save()
