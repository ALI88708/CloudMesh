import paramiko
import os
from pathlib import Path


class ServerManager:
    def __init__(self, security_manager):
        self.security = security_manager
        self.config = self.security.load_config()
        self._connections = {}

    def _save(self):
        self.security.save_config(self.config)

    def add_server(self, name, host, user, port=22, key_path=None, password=None):
        if name in self.config["servers"]:
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
        self.config["servers"][name] = server_info
        self._save()

    def remove_server(self, name):
        if name not in self.config["servers"]:
            raise ValueError(f"Server '{name}' not found")
        self.disconnect(name)
        del self.config["servers"][name]
        self._save()

    def list_servers(self):
        return list(self.config["servers"].keys())

    def get_server_info(self, name):
        if name not in self.config["servers"]:
            raise ValueError(f"Server '{name}' not found")
        return self.config["servers"][name]

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
        client.set_missing_host_key_policy(paramiko.WarningPolicy())

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
        self.config["servers"][name]["status"] = "connected"
        self._save()
        return client

    def disconnect(self, name):
        if name in self._connections:
            try:
                self._connections[name].close()
            except Exception:
                pass
            del self._connections[name]
            if name in self.config["servers"]:
                self.config["servers"][name]["status"] = "disconnected"

    def disconnect_all(self):
        for name in list(self._connections.keys()):
            self.disconnect(name)

    def execute(self, name, command):
        client = self.connect(name)
        stdin, stdout, stderr = client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        return {"exit_code": exit_code, "stdout": out, "stderr": err}

    def test_connection(self, name):
        try:
            result = self.execute(name, "echo connected")
            if result["exit_code"] == 0 and result["stdout"] == "connected":
                self.config["servers"][name]["status"] = "connected"
                self._save()
                return True, "Connection successful"
        except paramiko.AuthenticationException:
            self.config["servers"][name]["status"] = "auth_failed"
            self._save()
            return False, "Authentication failed"
        except paramiko.SSHException as e:
            self.config["servers"][name]["status"] = "error"
            self._save()
            return False, f"SSH error: {e}"
        except Exception as e:
            self.config["servers"][name]["status"] = "error"
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
            self.config["servers"][name]["os_type"] = os_type
            self._save()
            return os_type
        except Exception:
            return "unknown"
