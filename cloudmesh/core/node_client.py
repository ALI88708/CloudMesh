import hashlib
import hmac as hmac_mod
import json
import os
import secrets
import socket
import ssl
import tempfile
import time
import uuid
from pathlib import Path

try:
    from cloudmesh.core import node_relay
    from cloudmesh.core.storage import resolve_base_dir
except ImportError:  # pragma: no cover - source checkout without installed package
    from core import node_relay
    from core.storage import resolve_base_dir

MAX_RESPONSE_BYTES = 50 * 1024 * 1024
CLIENT_ID = secrets.token_hex(16)


def save_private_json(path, data):
    path = Path(path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as json_file:
            json.dump(data, json_file, indent=2)
        os.replace(temporary_path, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


class NodeClient:
    def __init__(
        self,
        host,
        port=9999,
        auth_key=None,
        tls=False,
        ca_file=None,
        transport="direct",
        relay_entry=None,
        relay_profile=None,
        relay_error=None,
        client_id=None,
    ):
        self.host = host
        self.port = port
        self.auth_key = auth_key
        self.tls = tls
        self.ca_file = ca_file
        self.transport = transport
        self.relay_entry = relay_entry
        self.relay_profile = relay_profile
        self.relay_error = relay_error
        self.last_error = relay_error
        # Configuration errors are permanent: retrying cannot fix a missing
        # profile or a malformed sidecar. Transport errors are not, so they are
        # cleared before every attempt.
        self._config_error = relay_error
        self.client_id = client_id or CLIENT_ID
        self._ssl_context = (
            ssl.create_default_context(cafile=ca_file) if tls else None
        )
        self._key_file = resolve_base_dir() / ".node_keys.json"
        self._keys = self._load_keys()

    @classmethod
    def from_config(cls, node, name=None):
        direct = {
            "host": node["host"],
            "port": node.get("port", 9999),
            "auth_key": node.get("key"),
            "tls": node.get("tls", False),
            "ca_file": node.get("ca_file"),
        }
        if name is None:
            return cls(**direct)

        store = node_relay.NodeRelayStore()
        entries = store.load()
        if store.last_error:
            return cls(
                **direct,
                transport="relay",
                relay_error=f"relay config is corrupt: {store.last_error}",
            )
        entry = entries.get(name)
        if entry is None:
            return cls(**direct)

        missing = [
            field
            for field in ("relay_id", "url", "relay_fingerprint", "node_fingerprint")
            if not entry.get(field)
        ]
        if missing:
            return cls(
                **direct,
                transport="relay",
                relay_entry=entry,
                relay_error=(
                    "relay config is incomplete: missing " + ", ".join(missing)
                ),
            )

        profiles = node_relay.RelayProfileStore()
        profile = profiles.get(entry["url"])
        if profiles.last_error:
            return cls(
                **direct,
                transport="relay",
                relay_entry=entry,
                relay_error=f"relay profile is corrupt: {profiles.last_error}",
            )
        if profile is None:
            return cls(
                **direct,
                transport="relay",
                relay_entry=entry,
                relay_error=f"relay profile is missing for {entry['url']}",
            )
        return cls(
            **direct,
            transport="relay",
            relay_entry=entry,
            relay_profile=profile,
        )

    def _load_keys(self):
        if self._key_file.exists():
            try:
                return json.loads(self._key_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_keys(self):
        save_private_json(self._key_file, self._keys)

    def set_key(self, node_name, auth_key):
        self._keys[node_name] = {"host": self.host, "port": self.port, "key": auth_key}
        self._save_keys()

    def get_key(self, node_name):
        if node_name in self._keys:
            info = self._keys[node_name]
            return info.get("key")
        return self.auth_key

    @staticmethod
    def send_spa_knock(host, auth_key, spa_port=9998):
        timestamp = time.time()
        nonce = uuid.uuid4().hex[:16]
        msg = f"{timestamp}:{nonce}"
        signature = hmac_mod.new(
            auth_key.encode(), msg.encode(), hashlib.sha256
        ).hexdigest()
        packet = json.dumps({
            "timestamp": timestamp,
            "nonce": nonce,
            "hmac": signature,
        }).encode()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(packet, (host, spa_port))
        finally:
            sock.close()

    def _send(self, request, timeout=10, spa=False, spa_port=9998, spa_delay=0.5):
        if self.transport == "relay":
            return self._send_relay(request, timeout)

        if spa:
            self.send_spa_knock(self.host, self.auth_key or "", spa_port)
            time.sleep(spa_delay)

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((self.host, self.port))
            if self._ssl_context is not None:
                sock = self._ssl_context.wrap_socket(
                    sock, server_hostname=self.host
                )
            return self._send_on_socket(sock, request, timeout)
        except TimeoutError:
            return {
                "type": "error",
                "message": "Connection timed out",
                "request_sent": False,
            }
        except ConnectionRefusedError:
            if spa:
                message = "Connection refused — TCP port may not be open yet (try increasing --spa-delay)"
            else:
                message = "Connection refused - is the node running?"
            return {"type": "error", "message": message, "request_sent": False}
        except Exception as e:
            return {
                "type": "error",
                "message": str(e),
                "request_sent": False,
            }
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def _send_on_socket(self, sock, request, timeout=10):
        request_sent = False
        try:
            sock.settimeout(timeout)
            msg = json.dumps(request).encode()
            sock.sendall(len(msg).to_bytes(4, "big") + msg)
            request_sent = True
            length_bytes = b""
            while len(length_bytes) < 4:
                chunk = sock.recv(4 - len(length_bytes))
                if not chunk:
                    return {
                        "type": "error",
                        "message": "Incomplete response header",
                        "request_sent": request_sent,
                    }
                length_bytes += chunk
            length = int.from_bytes(length_bytes, "big")
            if length > MAX_RESPONSE_BYTES:
                return {
                    "type": "error",
                    "message": f"Response too large ({length} bytes)",
                    "request_sent": request_sent,
                }
            data = b""
            while len(data) < length:
                chunk = sock.recv(min(length - len(data), 65536))
                if not chunk:
                    return {
                        "type": "error",
                        "message": "Incomplete response body",
                        "request_sent": request_sent,
                    }
                data += chunk
            return json.loads(data.decode())
        except TimeoutError:
            return {
                "type": "error",
                "message": "Connection timed out",
                "request_sent": request_sent,
            }
        except OSError as exc:
            return {
                "type": "error",
                "message": str(exc),
                "request_sent": request_sent,
            }
        except ValueError as exc:
            return {
                "type": "error",
                "message": str(exc),
                "request_sent": request_sent,
            }

    def _open_relay(self, timeout):
        """Pair through the relay, retrying once for availability failures.

        A node re-parks between sessions, so one failed pairing is usually the
        instant between a finished request and the next parked connection. A
        certificate identity mismatch is a trust decision, not an availability
        blip, and is raised at once. Pairing is capped at 15s even when the
        request timeout is minutes, so a dead relay fails fast.
        """
        pairing_timeout = min(timeout, 15.0)
        last_error = "relay pairing failed"
        for attempt in range(2):
            try:
                return node_relay.RelayTransport(
                    self.relay_entry or {},
                    self.relay_profile or {},
                    self.client_id,
                    timeout=pairing_timeout,
                ).connect()
            except node_relay.RelayError as exc:
                last_error = str(exc)
                if "identity mismatch" in last_error:
                    break
                if attempt == 0:
                    time.sleep(0.25)
        raise node_relay.RelayError(last_error)

    def _send_relay(self, request, timeout=10):
        if self._config_error:
            return {
                "type": "error",
                "message": self._config_error,
                "request_sent": False,
            }
        self.last_error = None
        try:
            sock = self._open_relay(timeout)
        except node_relay.RelayError as exc:
            self.last_error = str(exc)
            return {
                "type": "error",
                "message": str(exc),
                "request_sent": False,
            }
        try:
            result = self._send_on_socket(sock, request, timeout)
            if result.get("type") == "error" and not result.get("request_sent"):
                self.last_error = result.get("message") or "relay request failed"
            return result
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def ping(self, auth_key=None, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({"action": "ping", "auth": key}, spa=spa, spa_port=spa_port)
        return resp.get("type") == "pong"

    def get_metrics(self, auth_key=None, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({"action": "metrics", "auth": key}, timeout=15, spa=spa, spa_port=spa_port)
        if resp.get("type") == "metrics":
            return resp.get("data")
        return None

    def execute(self, command, auth_key=None, timeout=300, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "execute",
            "auth": key,
            "command": command,
            "timeout": timeout,
        }, timeout=timeout + 10, spa=spa, spa_port=spa_port)
        return resp.get("data", resp)

    def get_info(self, auth_key=None, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({"action": "info", "auth": key}, spa=spa, spa_port=spa_port)
        if resp.get("type") == "info":
            return resp.get("data")
        return None

    def upload_file(self, remote_path, content, auth_key=None, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "upload",
            "auth": key,
            "data": {"path": remote_path, "content": content},
        }, spa=spa, spa_port=spa_port)
        return resp.get("data", resp)

    def download_file(self, remote_path, auth_key=None, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "download",
            "auth": key,
            "data": {"path": remote_path},
        }, spa=spa, spa_port=spa_port)
        return resp.get("data", resp)

    def get_gpu(self, auth_key=None, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({"action": "gpu", "auth": key}, timeout=10, spa=spa, spa_port=spa_port)
        if resp.get("type") == "gpu":
            return resp.get("data")
        return None

    def start_job(self, command, auth_key=None, timeout=300, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "start_job",
            "auth": key,
            "command": command,
            "timeout": timeout,
        }, timeout=30, spa=spa, spa_port=spa_port)
        return resp.get("data", resp)

    def check_job(self, job_id, auth_key=None, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "check_job",
            "auth": key,
            "job_id": job_id,
        }, timeout=10, spa=spa, spa_port=spa_port)
        return resp.get("data", resp)

    def list_jobs(self, auth_key=None, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "list_jobs",
            "auth": key,
        }, timeout=10, spa=spa, spa_port=spa_port)
        return resp.get("data", resp)

    def kill_job(self, job_id, auth_key=None, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "kill_job",
            "auth": key,
            "job_id": job_id,
        }, timeout=10, spa=spa, spa_port=spa_port)
        return resp.get("data", resp)

    def rotate_keys(self, auth_key=None, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "rotate_keys",
            "auth": key,
        }, timeout=10, spa=spa, spa_port=spa_port)
        return resp.get("data", resp)

    def rotate_key(self, new_key, auth_key=None, spa=False, spa_port=9998):
        key = auth_key or self.auth_key
        resp = self._send({
            "action": "rotate_key",
            "auth": key,
            "new_key": new_key,
        }, timeout=10, spa=spa, spa_port=spa_port)
        return resp.get("data", resp)
