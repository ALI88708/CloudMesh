"""CloudMesh Security Test Suite

Tests critical security invariants:
- API endpoints reject unauthorized requests (401)
- Node rejects wrong auth keys
- Path traversal is blocked in file upload/download
- ACL permission checks work correctly
"""

import hashlib
import hmac
import json
import os
import secrets
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────
# 1. REST API Auth Tests
# ─────────────────────────────────────────────

class FakeRequest:
    def __init__(self, path="/api/status", headers=None):
        self.path = path
        self.headers = headers or {}


def _make_api(api_key=None):
    from core.advanced import CloudMeshAPI
    key = api_key or secrets.token_hex(32)
    return CloudMeshAPI(api_key=key), key


class TestAPIAuth:
    def test_no_key_returns_401(self):
        api, _ = _make_api()
        result = api._handle(FakeRequest("/api/status"))
        assert isinstance(result, tuple)
        assert result[1] == 401
        assert result[0]["error"] == "Unauthorized"

    def test_wrong_key_returns_401(self):
        api, _ = _make_api()
        result = api._handle(FakeRequest("/api/status", {"X-Api-Key": "wrong_key_here"}))
        assert isinstance(result, tuple)
        assert result[1] == 401

    def test_empty_key_returns_401(self):
        api, _ = _make_api()
        result = api._handle(FakeRequest("/api/status", {"X-Api-Key": ""}))
        assert isinstance(result, tuple)
        assert result[1] == 401

    def test_valid_key_returns_200(self):
        api, key = _make_api()
        result = api._handle(FakeRequest("/api/status", {"X-Api-Key": key}))
        assert isinstance(result, dict)
        assert result["status"] == "ok"

    def test_exec_endpoint_no_key_returns_401(self):
        api, _ = _make_api()
        result = api._handle(FakeRequest("/api/exec/myserver?cmd=whoami"))
        assert isinstance(result, tuple)
        assert result[1] == 401

    def test_exec_endpoint_valid_key_no_server(self):
        api, key = _make_api()
        result = api._handle(FakeRequest("/api/exec/nonexistent?cmd=whoami", {"X-Api-Key": key}))
        assert isinstance(result, dict)
        assert "not found" in result["error"].lower()

    def test_nodes_endpoint_no_key_leaks_nothing(self):
        api, _ = _make_api()
        api.node_keys = {"test": {"host": "1.2.3.4", "port": 9999, "key": "SECRETKEY"}}
        result = api._handle(FakeRequest("/api/nodes"))
        assert isinstance(result, tuple)
        assert result[1] == 401

    def test_nodes_endpoint_safe_output(self):
        api, key = _make_api()
        api.node_keys = {"test": {"host": "1.2.3.4", "port": 9999, "key": "SECRETKEY"}}
        result = api._handle(FakeRequest("/api/nodes", {"X-Api-Key": key}))
        assert isinstance(result, dict)
        node = result["nodes"]["test"]
        assert "key" not in node
        assert node["host"] == "1.2.3.4"


# ─────────────────────────────────────────────
# 2. Path Traversal Tests
# ─────────────────────────────────────────────

class TestPathTraversal:
    def test_dotdot_slash_etc_passwd(self):
        sys.path.insert(0, str(ROOT / "node"))
        from cloudmesh_node import _safe_path
        result = _safe_path("../../etc/passwd")
        assert result is None

    def test_absolute_path_outside_data(self):
        sys.path.insert(0, str(ROOT / "node"))
        from cloudmesh_node import _safe_path
        result = _safe_path("/etc/passwd")
        assert result is None

    def test_dotdot_in_middle(self):
        sys.path.insert(0, str(ROOT / "node"))
        from cloudmesh_node import _safe_path
        result = _safe_path("data/../../etc/shadow")
        assert result is None

    def test_symlink_escape(self):
        sys.path.insert(0, str(ROOT / "node"))
        from cloudmesh_node import _safe_path
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            outside = Path(tmp) / "secret.txt"
            outside.write_text("leaked")
            link = data_dir / "link"
            try:
                link.symlink_to(outside)
                result = _safe_path(str(link))
                if os.name != "nt":
                    assert result is None
            except OSError:
                pass

    def test_valid_path_inside_data(self):
        sys.path.insert(0, str(ROOT / "node"))
        from cloudmesh_node import _safe_path, BASE_DIR
        data_dir = BASE_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        result = _safe_path(str(data_dir / "test.txt"))
        assert result is not None
        assert "test.txt" in str(result)


# ─────────────────────────────────────────────
# 3. Node Auth Tests
# ─────────────────────────────────────────────

class TestNodeAuth:
    def test_hmac_compare_in_node(self):
        node_src = (ROOT / "node" / "cloudmesh_node.py").read_text()
        assert "compare_digest" in node_src

    def test_auth_rejects_wrong_key(self):
        sys.path.insert(0, str(ROOT / "node"))
        from cloudmesh_node import NodeAgent
        import socket, json

        correct_key = "valid_secret_key"
        node = NodeAgent(port=0, auth_key=correct_key, bind_host="127.0.0.1")

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)

        result = {}

        def client_thread():
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.connect(("127.0.0.1", port))
            msg = json.dumps({"action": "ping", "auth": "wrong_key"}).encode()
            c.sendall(len(msg).to_bytes(4, "big") + msg)
            c.settimeout(3)
            try:
                header = b""
                while len(header) < 4:
                    chunk = c.recv(4 - len(header))
                    if not chunk:
                        break
                    header += chunk
                length = int.from_bytes(header, "big")
                data = b""
                while len(data) < length:
                    chunk = c.recv(min(length - len(data), 65536))
                    if not chunk:
                        break
                    data += chunk
                result["response"] = json.loads(data.decode())
            except Exception as e:
                result["error"] = str(e)
            finally:
                c.close()

        t = threading.Thread(target=client_thread, daemon=True)
        t.start()
        try:
            conn, addr = srv.accept()
            node._handle(conn, addr)
        except Exception:
            pass
        t.join(timeout=5)
        srv.close()
        assert result.get("response", {}).get("type") == "error"
        assert "auth" in result.get("response", {}).get("message", "").lower()

    def test_auth_rejects_empty_key(self):
        sys.path.insert(0, str(ROOT / "node"))
        from cloudmesh_node import NodeAgent
        import socket, json

        node = NodeAgent(port=0, auth_key="correct_key", bind_host="127.0.0.1")

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)

        result = {}

        def client_thread():
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.connect(("127.0.0.1", port))
            msg = json.dumps({"action": "ping", "auth": ""}).encode()
            c.sendall(len(msg).to_bytes(4, "big") + msg)
            c.settimeout(3)
            try:
                header = b""
                while len(header) < 4:
                    chunk = c.recv(4 - len(header))
                    if not chunk:
                        break
                    header += chunk
                length = int.from_bytes(header, "big")
                data = b""
                while len(data) < length:
                    chunk = c.recv(min(length - len(data), 65536))
                    if not chunk:
                        break
                    data += chunk
                result["response"] = json.loads(data.decode())
            except Exception as e:
                result["error"] = str(e)
            finally:
                c.close()

        t = threading.Thread(target=client_thread, daemon=True)
        t.start()
        try:
            conn, addr = srv.accept()
            node._handle(conn, addr)
        except Exception:
            pass
        t.join(timeout=5)
        srv.close()
        assert result.get("response", {}).get("type") == "error"

    def test_auth_accepts_correct_key(self):
        sys.path.insert(0, str(ROOT / "node"))
        from cloudmesh_node import NodeAgent
        import socket, json

        correct_key = "valid_secret_key"
        node = NodeAgent(port=0, auth_key=correct_key, bind_host="127.0.0.1")

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)

        result = {}

        def client_thread():
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.connect(("127.0.0.1", port))
            msg = json.dumps({"action": "ping", "auth": correct_key}).encode()
            c.sendall(len(msg).to_bytes(4, "big") + msg)
            c.settimeout(3)
            try:
                header = b""
                while len(header) < 4:
                    chunk = c.recv(4 - len(header))
                    if not chunk:
                        break
                    header += chunk
                length = int.from_bytes(header, "big")
                data = b""
                while len(data) < length:
                    chunk = c.recv(min(length - len(data), 65536))
                    if not chunk:
                        break
                    data += chunk
                result["response"] = json.loads(data.decode())
            except Exception as e:
                result["error"] = str(e)
            finally:
                c.close()

        t = threading.Thread(target=client_thread, daemon=True)
        t.start()
        try:
            conn, addr = srv.accept()
            node._handle(conn, addr)
        except Exception:
            pass
        t.join(timeout=5)
        srv.close()
        assert result.get("response", {}).get("type") == "pong"


# ─────────────────────────────────────────────
# 4. ACL Tests
# ─────────────────────────────────────────────

class TestACL:
    def _make_acl(self, tmp_path, monkeypatch):
        import core.acl as acl_mod
        monkeypatch.setattr(acl_mod, "DATA_DIR", str(tmp_path))
        return acl_mod

    def test_add_and_authenticate_user(self, tmp_path, monkeypatch):
        mod = self._make_acl(tmp_path, monkeypatch)
        result = mod.add_user("alice", "password123", "admin")
        assert "created" in result.lower()
        assert mod.authenticate("alice", "password123") is True
        assert mod.authenticate("alice", "wrongpass") is False

    def test_disabled_user_cannot_authenticate(self, tmp_path, monkeypatch):
        mod = self._make_acl(tmp_path, monkeypatch)
        mod.add_user("bob", "pass123", "viewer")
        mod.disable_user("bob")
        assert mod.authenticate("bob", "pass123") is False
        mod.enable_user("bob")
        assert mod.authenticate("bob", "pass123") is True

    def test_admin_has_wildcard_permission(self, tmp_path, monkeypatch):
        mod = self._make_acl(tmp_path, monkeypatch)
        mod.add_user("admin1", "pass", "admin")
        assert mod.check_permission("admin1", "anything") is True

    def test_viewer_has_limited_permission(self, tmp_path, monkeypatch):
        mod = self._make_acl(tmp_path, monkeypatch)
        mod.add_user("viewer1", "pass", "viewer")
        assert mod.check_permission("viewer1", "monitor") is True
        assert mod.check_permission("viewer1", "deploy") is False

    def test_remove_user(self, tmp_path, monkeypatch):
        mod = self._make_acl(tmp_path, monkeypatch)
        mod.add_user("temp_user", "pass", "viewer")
        mod.remove_user("temp_user")
        assert mod.authenticate("temp_user", "pass") is False

    def test_duplicate_user_rejected(self, tmp_path, monkeypatch):
        mod = self._make_acl(tmp_path, monkeypatch)
        mod.add_user("dup", "pass1", "viewer")
        result = mod.add_user("dup", "pass2", "admin")
        assert "already exists" in result.lower()

    def test_roles_permissions(self, tmp_path, monkeypatch):
        mod = self._make_acl(tmp_path, monkeypatch)
        mod.add_role("deployer", ["deploy", "run", "monitor"])
        mod.add_user("dev1", "pass", "deployer")
        assert mod.check_permission("dev1", "deploy") is True
        assert mod.check_permission("dev1", "delete") is False


# ─────────────────────────────────────────────
# 5. HMAC Comparison Tests
# ─────────────────────────────────────────────

class TestHMACComparison:
    def test_compare_digest_used_for_api_key(self):
        from core.advanced import CloudMeshAPI
        import inspect
        src = inspect.getsource(CloudMeshAPI._handle)
        assert "compare_digest" in src

    def test_compare_digest_used_for_node_auth(self):
        node_src = (ROOT / "node" / "cloudmesh_node.py").read_text()
        assert "compare_digest" in node_src

    def test_compare_digest_in_start_handler(self):
        from core.advanced import CloudMeshAPI
        import inspect
        src = inspect.getsource(CloudMeshAPI.start)
        assert "compare_digest" in src
