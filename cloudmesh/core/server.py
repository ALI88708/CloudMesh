import paramiko
import os
import logging
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

try:
    from cloudmesh.core.storage import StorageManager
except ImportError:  # `cd cloudmesh && pytest tests` without installed package
    from core.storage import StorageManager

logger = logging.getLogger(__name__)


class ServerManager:
    """Manage servers with SQLite as the only server registry.

    CloudMesh 5 imports a legacy JSON `servers` mapping once and then removes
    it. Other configuration remains in `config.json`; server records never do.
    """

    _LEGACY_FIELDS = ("host", "user", "port", "key_path", "password", "status", "os_type")

    def __init__(self, security_manager, storage=None):
        self.security = security_manager
        self.config = self.security.load_config()
        if storage is None:
            storage = StorageManager(self.security.base_dir)
        self.storage = storage
        self._connections = {}
        self._state_lock = threading.RLock()
        if self._import_legacy_servers():
            self._drop_legacy_registry()

    def _import_legacy_servers(self):
        """Import JSON servers once and report whether SQLite is authoritative.

        The JSON copy is removed only after a complete import or when the
        persistent marker already exists. A failed import leaves it intact so
        a database problem cannot destroy the only remaining server list.
        """
        try:
            if self.storage.legacy_imported("servers"):
                return True
        except Exception:
            return False

        for name, info in list(self.config.get("servers", {}).items()):
            if not isinstance(info, dict):
                continue
            try:
                if not self.storage.add_server(
                    name=name,
                    host=info.get("host"),
                    user=info.get("user"),
                    port=info.get("port", 22),
                    key_path=info.get("key_path"),
                    password=info.get("password"),
                ):
                    raise RuntimeError("storage rejected server")
            except Exception:
                logger.warning("Servers import incomplete; legacy JSON retained")
                return False
        try:
            self.storage.mark_legacy_imported("servers")
        except Exception:
            return False
        return True

    def _drop_legacy_registry(self):
        """Remove the migrated JSON server mapping, keeping other settings."""
        if "servers" not in self.config:
            return
        self.config.pop("servers")
        self.security.save_config(self.config)

    def add_server(self, name, host, user, port=22, key_path=None, password=None):
        if self.storage.get_server(name) is not None:
            raise ValueError(f"Server '{name}' already exists")
        if not self.storage.add_server(
            name=name,
            host=host,
            user=user,
            port=port,
            key_path=str(key_path) if key_path else None,
            password=password,
        ):
            raise ValueError(f"Server '{name}' already exists")

    def remove_server(self, name):
        if self.storage.get_server(name) is None:
            raise ValueError(f"Server '{name}' not found")
        self.disconnect(name)
        self.storage.remove_server(name)

    def list_servers(self):
        try:
            return [s["name"] for s in self.storage.list_servers()]
        except Exception:
            return []

    def get_server_info(self, name):
        try:
            info = self.storage.get_server(name)
        except Exception:
            info = None
        if info is None:
            raise ValueError(f"Server '{name}' not found")
        legacy = {k: info.get(k) for k in self._LEGACY_FIELDS}
        if legacy.get("port") is None:
            legacy["port"] = 22
        return legacy

    def _set_status(self, name, status):
        with self._state_lock:
            try:
                self.storage.update_server_status(name, status)
            except Exception:
                pass

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

    def execute(self, name, command, timeout=None):
        """Run a command over SSH on the named server and wait for completion.

        Return `exit_code`, `stdout`, and `stderr`; decode both streams as UTF-8
        and strip surrounding whitespace. Nonzero exit codes are returned.
        `timeout` bounds the remote read (not the connect), and a timeout raises
        `socket.timeout` so the caller can report it as a failed target.
        An unknown server raises ValueError when connecting; connection,
        configuration persistence, command execution, and decoding errors propagate.
        """
        client = self.connect(name)
        # nosec B601 -- this is the SSH administration tool's primary verb: the
        # command comes from the operator, who already holds the key that
        # authenticated the session. Reaching this line requires an existing
        # authenticated session, not attacker-supplied input.
        if timeout is None:
            stdin, stdout, stderr = client.exec_command(command)  # nosec B601
        else:
            stdin, stdout, stderr = client.exec_command(  # nosec B601
                command, timeout=timeout
            )
        with ThreadPoolExecutor(max_workers=2) as executor:
            stdout_future = executor.submit(stdout.read)
            stderr_future = executor.submit(stderr.read)
            out = stdout_future.result().decode().strip()
            err = stderr_future.result().decode().strip()
        if timeout is None:
            exit_code = stdout.channel.recv_exit_status()
        else:
            # recv_exit_status() itself waits forever, so bound the event it
            # waits on. A command that closes its streams but never exits would
            # otherwise defeat --timeout.
            if not stdout.channel.status_event.wait(timeout):
                try:
                    stdout.channel.close()
                except Exception:
                    pass
                raise TimeoutError(
                    f"command did not finish within {timeout:g}s"
                )
            exit_code = stdout.channel.recv_exit_status()
        return {"exit_code": exit_code, "stdout": out, "stderr": err}

    def test_connection(self, name):
        try:
            result = self.execute(name, "echo connected")
            if result["exit_code"] == 0 and result["stdout"] == "connected":
                self._set_status(name, "connected")
                return True, "Connection successful"
        except paramiko.AuthenticationException:
            self._set_status(name, "auth_failed")
            return False, "Authentication failed"
        except paramiko.SSHException as e:
            self._set_status(name, "error")
            return False, f"SSH error: {e}"
        except Exception as e:
            self._set_status(name, "error")
            return False, f"Error: {e}"
        return False, "Unknown error"

    def detect_os(self, name):
        try:
            result = self.execute(name, "uname -s 2>/dev/null || echo windows")
            uname = result["stdout"].lower()
            if "freebsd" in uname:
                os_type = "freebsd"
            elif "openbsd" in uname:
                os_type = "openbsd"
            elif "netbsd" in uname:
                os_type = "netbsd"
            elif "linux" in uname or "darwin" in uname:
                os_type = "linux"
            else:
                os_type = "windows"
            try:
                self.storage.update_server_os_type(name, os_type)
            except Exception:
                pass
            return os_type
        except Exception:
            return "unknown"
