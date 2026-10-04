import paramiko
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

try:
    from cloudmesh.core.storage import StorageManager
except ImportError:  # `cd cloudmesh && pytest tests` without installed package
    from core.storage import StorageManager


class ServerManager:
    """Manage servers with SQLite as the source of truth.

    Server records live in StorageManager (encrypted secrets). The legacy
    JSON config is kept as a compatible mirror so older readers keep working,
    and any legacy JSON servers are imported once into SQLite on init.
    """

    _LEGACY_FIELDS = ("host", "user", "port", "key_path", "password", "status", "os_type")

    def __init__(self, security_manager, storage=None):
        self.security = security_manager
        self.config = self.security.load_config()
        if "servers" not in self.config:
            self.config["servers"] = {}
        if storage is None:
            storage = StorageManager(self.security.base_dir)
        self.storage = storage
        self._connections = {}
        self._import_legacy_servers()

    def _import_legacy_servers(self):
        """Import JSON-config servers into SQLite once (guarded by a marker).

        An empty servers table is a valid state (e.g. after restoring a
        backup with no servers), so the persistent marker — not table
        emptiness — decides whether the legacy import runs. When the marker
        is present, SQLite is authoritative and the JSON mirror is repaired
        from it instead.
        """
        try:
            if self.storage.legacy_imported("servers"):
                self._push_mirror_from_storage()
                return
        except Exception:
            return
        for name, info in list(self.config.get("servers", {}).items()):
            if not isinstance(info, dict):
                continue
            try:
                self.storage.add_server(
                    name=name,
                    host=info.get("host"),
                    user=info.get("user"),
                    port=info.get("port", 22),
                    key_path=info.get("key_path"),
                    password=info.get("password"),
                )
            except Exception:
                continue
        try:
            self.storage.mark_legacy_imported("servers")
        except Exception:
            pass
        self._push_mirror_from_storage()

    def _push_mirror_from_storage(self):
        """Repair the JSON mirror from SQLite (SQLite wins)."""
        try:
            rows = {
                s["name"]: {k: s.get(k) for k in self._LEGACY_FIELDS}
                for s in self.storage.list_servers()
            }
        except Exception:
            return
        if rows != self.config.get("servers", {}):
            self.config["servers"] = rows
            try:
                self._save()
            except Exception:
                pass

    def _save(self):
        self.security.save_config(self.config)

    def _mirror_to_config(self, name, info):
        self.config.setdefault("servers", {})[name] = {
            k: info.get(k) for k in self._LEGACY_FIELDS
        }

    def add_server(self, name, host, user, port=22, key_path=None, password=None):
        if self.storage.get_server(name) is not None or name in self.config["servers"]:
            raise ValueError(f"Server '{name}' already exists")
        server_info = {
            "host": host,
            "user": user,
            "port": port,
            "key_path": str(key_path) if key_path else None,
            "password": password,
            "status": "unknown",
            "os_type": "linux",
        }
        if not self.storage.add_server(
            name=name, host=host, user=user, port=port,
            key_path=server_info["key_path"], password=password,
        ):
            raise ValueError(f"Server '{name}' already exists")
        self._mirror_to_config(name, server_info)
        self._save()

    def remove_server(self, name):
        if self.storage.get_server(name) is None and name not in self.config["servers"]:
            raise ValueError(f"Server '{name}' not found")
        self.disconnect(name)
        self.storage.remove_server(name)
        self.config["servers"].pop(name, None)
        self._save()

    def list_servers(self):
        try:
            names = [s["name"] for s in self.storage.list_servers()]
            if names:
                return names
        except Exception:
            pass
        return list(self.config["servers"].keys())

    def get_server_info(self, name):
        try:
            info = self.storage.get_server(name)
        except Exception:
            info = None
        if info is not None:
            legacy = {k: info.get(k) for k in self._LEGACY_FIELDS}
            if legacy.get("port") is None:
                legacy["port"] = 22
            return legacy
        if name not in self.config["servers"]:
            raise ValueError(f"Server '{name}' not found")
        return self.config["servers"][name]

    def _set_status(self, name, status):
        try:
            self.storage.update_server_status(name, status)
        except Exception:
            pass
        self._ensure_mirror(name)
        if name in self.config["servers"]:
            self.config["servers"][name]["status"] = status

    def _ensure_mirror(self, name):
        """Create the JSON mirror entry from SQLite if missing."""
        if name in self.config["servers"]:
            return
        try:
            info = self.storage.get_server(name)
        except Exception:
            info = None
        if info is not None:
            self._mirror_to_config(name, {k: info.get(k) for k in self._LEGACY_FIELDS})

    def connect(self, name):
        if name in self._connections:
            try:
                transport = self._connections[name].get_transport()
                if transport and transport.is_active():
                    return self._connections[name]
                else:
                    del self._connections[name]
            except Exception:
                del self._connections[name]

        info = self.get_server_info(name)
        client = paramiko.SSHClient()
        known_hosts_file = os.path.expanduser("~/.ssh/known_hosts")
        if os.path.exists(known_hosts_file):
            client.load_system_host_keys(known_hosts_file)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

        connect_kwargs = {
            "hostname": info["host"],
            "port": info.get("port", 22),
            "username": info["user"],
            "timeout": 10,
        }

        key_path = info.get("key_path")
        if key_path:
            expanded = os.path.expanduser(key_path)
            if os.path.exists(expanded):
                connect_kwargs["key_filename"] = expanded

        password = info.get("password")
        if password:
            connect_kwargs["password"] = password

        client.connect(**connect_kwargs)
        self._connections[name] = client
        self._set_status(name, "connected")
        self._save()
        return client

    def disconnect(self, name):
        if name in self._connections:
            try:
                self._connections[name].close()
            except Exception:
                pass
            del self._connections[name]
            self._set_status(name, "disconnected")

    def disconnect_all(self):
        for name in list(self._connections.keys()):
            self.disconnect(name)

    def execute(self, name, command):
        client = self.connect(name)
        stdin, stdout, stderr = client.exec_command(command)
        with ThreadPoolExecutor(max_workers=2) as executor:
            stdout_future = executor.submit(stdout.read)
            stderr_future = executor.submit(stderr.read)
            out = stdout_future.result().decode().strip()
            err = stderr_future.result().decode().strip()
        exit_code = stdout.channel.recv_exit_status()
        return {"exit_code": exit_code, "stdout": out, "stderr": err}

    def test_connection(self, name):
        try:
            result = self.execute(name, "echo connected")
            if result["exit_code"] == 0 and result["stdout"] == "connected":
                self._set_status(name, "connected")
                self._save()
                return True, "Connection successful"
        except paramiko.AuthenticationException:
            self._set_status(name, "auth_failed")
            self._save()
            return False, "Authentication failed"
        except paramiko.SSHException as e:
            self._set_status(name, "error")
            self._save()
            return False, f"SSH error: {e}"
        except Exception as e:
            self._set_status(name, "error")
            self._save()
            return False, f"Error: {e}"
        return False, "Unknown error"

    def detect_os(self, name):
        try:
            result = self.execute(name, "uname -s 2>/dev/null || echo windows")
            if "linux" in result["stdout"].lower() or "darwin" in result["stdout"].lower():
                os_type = "linux"
            else:
                os_type = "windows"
            try:
                self.storage.update_server_os_type(name, os_type)
            except Exception:
                pass
            self._ensure_mirror(name)
            if name in self.config["servers"]:
                self.config["servers"][name]["os_type"] = os_type
            self._save()
            return os_type
        except Exception:
            return "unknown"
