import socket
import json
import os
from pathlib import Path


class NodeClient:
    def __init__(self, host, port=9999, auth_key=None):
        self.host = host
        self.port = port
        self.auth_key = auth_key
        self._key_file = Path(__file__).parent.parent / ".node_keys.json"
        self._keys = self._load_keys()

    def _load_keys(self):
        if self._key_file.exists():
            try:
                return json.loads(self._key_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_keys(self):
        self._key_file.write_text(json.dumps(self._keys, indent=2))
        try:
            if os.name != "nt":
                os.chmod(self._key_file, 0o600)
        except Exception:
            pass

    def set_key(self, node_name, auth_key):
        self._keys[node_name] = {"host": self.host, "port": self.port, "key": auth_key}
        self._save_keys()

    def get_key(self, node_name):
        if node_name in self._keys:
            info = self._keys[node_name]
            return info.get("key")
        return self.auth_key

    def _send(self, request, timeout=10):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((self.host, self.port))
            msg = json.dumps(request).encode()
            sock.sendall(len(msg).to_bytes(4, 'big') + msg)
            length_bytes = sock.recv(4)
            if not length_bytes or len(length_bytes) < 4:
                return {"type": "error", "message": "No response from node"}
            length = int.from_bytes(length_bytes, 'big')
            data = b""
            while len(data) < length:
                chunk = sock.recv(min(length - len(data), 65536))
                if not chunk:
                    break
                data += chunk
            return json.loads(data.decode())
        except socket.timeout:
            return {"type": "error", "message": "Connection timed out"}
        except ConnectionRefusedError:
            return {"type": "error", "message": "Connection refused - is the node running?"}
        except Exception as e:
            return {"type": "error", "message": str(e)}
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def ping(self, auth_key=None):
        key = auth_key or self.auth_key
        resp = self._send({"action": "ping", "auth": key})
        return resp.get("type") == "pong"

    def get_metrics(self, auth_key=None):
        key = auth_key or self.auth_key
        resp = self._send({"action": "metrics", "auth": key}, timeout=15)
        if resp.get("type") == "metrics":
            return resp.get("data")
        return None

    def execute(self, command, auth_key=None, timeout=300):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "execute",
            "auth": key,
            "command": command,
            "timeout": timeout,
        }, timeout=timeout + 10)
        return resp.get("data", resp)

    def get_info(self, auth_key=None):
        key = auth_key or self.auth_key
        resp = self._send({"action": "info", "auth": key})
        if resp.get("type") == "info":
            return resp.get("data")
        return None

    def upload_file(self, remote_path, content, auth_key=None):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "upload",
            "auth": key,
            "data": {"path": remote_path, "content": content},
        })
        return resp.get("data", resp)

    def download_file(self, remote_path, auth_key=None):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "download",
            "auth": key,
            "data": {"path": remote_path},
        })
        return resp.get("data", resp)

    def get_gpu(self, auth_key=None):
        key = auth_key or self.auth_key
        resp = self._send({"action": "gpu", "auth": key}, timeout=10)
        if resp.get("type") == "gpu":
            return resp.get("data")
        return None

    def start_job(self, command, auth_key=None, timeout=300):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "start_job",
            "auth": key,
            "command": command,
            "timeout": timeout,
        }, timeout=30)
        return resp.get("data", resp)

    def check_job(self, job_id, auth_key=None):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "check_job",
            "auth": key,
            "job_id": job_id,
        }, timeout=10)
        return resp.get("data", resp)

    def list_jobs(self, auth_key=None):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "list_jobs",
            "auth": key,
        }, timeout=10)
        return resp.get("data", resp)

    def kill_job(self, job_id, auth_key=None):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "kill_job",
            "auth": key,
            "job_id": job_id,
        }, timeout=10)
        return resp.get("data", resp)
