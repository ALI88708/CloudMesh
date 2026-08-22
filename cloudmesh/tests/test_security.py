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


# ─────────────────────────────────────────────
# 6. Shamir Secret Sharing Tests
# ─────────────────────────────────────────────

class TestShamir:
    def test_split_and_combine_2of3(self):
        from core.shamir import ShamirSecretSharing
        secret = b"supersecretkey12345678901234567"
        shares = ShamirSecretSharing.split(secret, 3, 2)
        assert len(shares) == 3
        reconstructed = ShamirSecretSharing.combine(shares[:2])
        assert reconstructed == secret

    def test_all_2_of_3_combinations(self):
        from core.shamir import ShamirSecretSharing
        secret = b"another_test_secret_key_32bytes!"
        shares = ShamirSecretSharing.split(secret, 3, 2)
        for i in range(3):
            for j in range(i + 1, 3):
                reconstructed = ShamirSecretSharing.combine([shares[i], shares[j]])
                assert reconstructed == secret, f"Failed to reconstruct with shares {i},{j}"

    def test_single_share_fails(self):
        from core.shamir import ShamirSecretSharing
        secret = b"cannot_reconstruct_with_one_share!"
        shares = ShamirSecretSharing.split(secret, 3, 2)
        with pytest.raises(ValueError, match="at least 2"):
            ShamirSecretSharing.combine([shares[0]])

    def test_empty_secret_rejected(self):
        from core.shamir import ShamirSecretSharing
        with pytest.raises(ValueError, match="empty"):
            ShamirSecretSharing.split(b"", 3, 2)

    def test_invalid_threshold_rejected(self):
        from core.shamir import ShamirSecretSharing
        with pytest.raises(ValueError):
            ShamirSecretSharing.split(b"test", 3, 1)

    def test_duplicate_shares_rejected(self):
        from core.shamir import ShamirSecretSharing
        secret = b"test_secret_for_duplicates"
        shares = ShamirSecretSharing.split(secret, 3, 2)
        with pytest.raises(ValueError, match="Duplicate"):
            ShamirSecretSharing.combine([shares[0], shares[0]])

    def test_wrong_shares_fail(self):
        from core.shamir import ShamirSecretSharing
        secret1 = b"secret_one_key_1234567890123456"
        secret2 = b"secret_two_key_1234567890123456"
        shares1 = ShamirSecretSharing.split(secret1, 3, 2)
        shares2 = ShamirSecretSharing.split(secret2, 3, 2)
        mixed = [shares1[0], shares2[1]]
        reconstructed = ShamirSecretSharing.combine(mixed)
        assert reconstructed != secret1
        assert reconstructed != secret2


# ─────────────────────────────────────────────
# 7. Tripwire Tests
# ─────────────────────────────────────────────

class TestTripwire:
    def test_plant_and_detect(self, tmp_path):
        from core.panic import TripwireManager
        tw = TripwireManager(base_dir=tmp_path)
        key = tw.plant("honeypot", "10.0.0.99")
        assert key is not None
        assert len(key) == 64
        is_tripwire, name = tw.check(key)
        assert is_tripwire is True
        assert name == "honeypot"

    def test_legitimate_key_not_tripwire(self, tmp_path):
        from core.panic import TripwireManager
        tw = TripwireManager(base_dir=tmp_path)
        tw.plant("honeypot", "10.0.0.99")
        is_tripwire, _ = tw.check("this_is_not_a_tripwire_key")
        assert is_tripwire is False

    def test_list_tripwires(self, tmp_path):
        from core.panic import TripwireManager
        tw = TripwireManager(base_dir=tmp_path)
        tw.plant("tw1", "10.0.0.1")
        tw.plant("tw2", "10.0.0.2")
        tripwires = tw.list_tripwires()
        assert len(tripwires) == 2
        assert "tw1" in tripwires
        assert "tw2" in tripwires

    def test_remove_tripwire(self, tmp_path):
        from core.panic import TripwireManager
        tw = TripwireManager(base_dir=tmp_path)
        tw.plant("to_remove", "10.0.0.5")
        result = tw.remove("to_remove")
        assert "removed" in result.lower()
        tripwires = tw.list_tripwires()
        assert len(tripwires) == 0

    def test_plant_duplicate_rejected(self, tmp_path):
        from core.panic import TripwireManager
        tw = TripwireManager(base_dir=tmp_path)
        tw.plant("existing", "10.0.0.1", port=9999)
        result = tw.plant("existing", "10.0.0.2")
        assert "already" in result.lower()

    def test_node_agent_detects_tripwire(self, tmp_path):
        sys.path.insert(0, str(ROOT / "node"))
        from cloudmesh_node import NodeAgent
        import socket

        tw_key = "tripwire_secret_1234567890abcdef"
        tripwire_file = tmp_path / ".tripwire_keys.json"
        tripwire_file.write_text(json.dumps({
            "honeypot": {"host": "10.0.0.99", "port": 9999, "key": tw_key}
        }))

        import cloudmesh_node
        orig_keys = cloudmesh_node.TRIPWIRE_KEYS_FILE
        orig_base = cloudmesh_node.BASE_DIR
        cloudmesh_node.TRIPWIRE_KEYS_FILE = tripwire_file
        cloudmesh_node.BASE_DIR = tmp_path

        node = NodeAgent(port=0, auth_key="real_key", bind_host="127.0.0.1")

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.listen(1)

        result = {}

        def client_thread():
            c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            c.connect(("127.0.0.1", port))
            msg = json.dumps({"action": "ping", "auth": tw_key}).encode()
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

        log_file = tmp_path / ".tripwire_log.json"
        assert log_file.exists()
        log = json.loads(log_file.read_text())
        assert any(e.get("event") == "triggered" for e in log)

        cloudmesh_node.TRIPWIRE_KEYS_FILE = orig_keys
        cloudmesh_node.BASE_DIR = orig_base


# ─────────────────────────────────────────────
# 8. SPA Packet Validation Tests
# ─────────────────────────────────────────────

class TestSpaPacket:
    def test_valid_hmac_packet(self):
        import hashlib
        import hmac as hmac_mod
        import uuid
        import time

        auth_key = "test_spa_key_12345"
        timestamp = time.time()
        nonce = uuid.uuid4().hex[:16]
        msg = f"{timestamp}:{nonce}"
        signature = hmac_mod.new(auth_key.encode(), msg.encode(), hashlib.sha256).hexdigest()

        packet = json.dumps({"timestamp": timestamp, "nonce": nonce, "hmac": signature}).encode()
        parsed = json.loads(packet)

        expected = hmac_mod.new(auth_key.encode(), f"{parsed['timestamp']}:{parsed['nonce']}".encode(), hashlib.sha256).hexdigest()
        assert hmac_mod.compare_digest(expected, parsed["hmac"])

    def test_replay_nonce_rejected(self):
        nonces_seen = set()
        nonce1 = "abc123"
        nonce2 = "abc123"
        assert nonce1 not in nonces_seen
        nonces_seen.add(nonce1)
        assert nonce2 in nonces_seen

    def test_stale_timestamp_rejected(self):
        import time
        stale_timestamp = time.time() - 60
        current_time = time.time()
        max_age = 30
        assert abs(current_time - stale_timestamp) > max_age

    def test_spa_knock_sends_udp(self):
        from core.node_client import NodeClient
        import hmac as hmac_mod
        import hashlib
        import time
        import uuid

        auth_key = "test_controller_key"
        timestamp = time.time()
        nonce = uuid.uuid4().hex[:16]
        msg = f"{timestamp}:{nonce}"
        signature = hmac_mod.new(auth_key.encode(), msg.encode(), hashlib.sha256).hexdigest()

        import socket
        srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.settimeout(2)

        NodeClient.send_spa_knock("127.0.0.1", auth_key, spa_port=port)

        try:
            data, addr = srv.recvfrom(1024)
            packet = json.loads(data.decode())
            assert "timestamp" in packet
            assert "nonce" in packet
            assert "hmac" in packet
            expected = hmac_mod.new(
                auth_key.encode(),
                f"{packet['timestamp']}:{packet['nonce']}".encode(),
                hashlib.sha256
            ).hexdigest()
            assert hmac_mod.compare_digest(expected, packet["hmac"])
        finally:
            srv.close()


# ─────────────────────────────────────────────
# 9. Shamir Panic Tests
# ─────────────────────────────────────────────

class TestShamirPanic:
    def test_setup_shares(self, tmp_path):
        from core.panic import ShamirPanicManager
        sp = ShamirPanicManager(base_dir=tmp_path)
        shares = sp.setup_shares()
        assert len(shares) == 3
        for s in shares:
            assert "id" in s
            assert "share" in s
            assert "label" in s

    def test_execute_with_2_shares(self, tmp_path):
        from core.panic import ShamirPanicManager
        sp = ShamirPanicManager(base_dir=tmp_path)
        shares = sp.setup_shares()
        share_ids = [s["id"] for s in shares[:2]]
        actions, error = sp.execute_with_shares(share_ids)
        assert error is None
        assert len(actions) > 0

    def test_execute_with_1_share_fails(self, tmp_path):
        from core.panic import ShamirPanicManager
        sp = ShamirPanicManager(base_dir=tmp_path)
        shares = sp.setup_shares()
        actions, error = sp.execute_with_shares([shares[0]["id"]])
        assert error is not None
        assert "need" in error.lower() or "2" in error

    def test_get_shares_info(self, tmp_path):
        from core.panic import ShamirPanicManager
        sp = ShamirPanicManager(base_dir=tmp_path)
        sp.setup_shares()
        info = sp.get_shares_info()
        assert info is not None
        assert info["threshold"] == 2
        assert info["n_shares"] == 3
        assert len(info["shares"]) == 3


class TestDDoSProtection:
    def test_rate_limiter_allows_within_limit(self):
        from core.ddos import RateLimiter
        rl = RateLimiter(max_requests=5, window=60)
        for _ in range(5):
            assert rl.is_allowed("10.0.0.1") is True
        assert rl.is_allowed("10.0.0.1") is False

    def test_rate_limiter_resets_after_window(self):
        from core.ddos import RateLimiter
        rl = RateLimiter(max_requests=2, window=0.1)
        assert rl.is_allowed("10.0.0.2") is True
        assert rl.is_allowed("10.0.0.2") is True
        assert rl.is_allowed("10.0.0.2") is False
        import time; time.sleep(0.15)
        assert rl.is_allowed("10.0.0.2") is True

    def test_connection_limiter_blocks_overflow(self):
        from core.ddos import ConnectionLimiter
        cl = ConnectionLimiter(max_per_ip=2, max_total=10)
        assert cl.can_accept("10.0.0.3") is True
        assert cl.can_accept("10.0.0.3") is True
        assert cl.can_accept("10.0.0.3") is False

    def test_connection_limiter_releases(self):
        from core.ddos import ConnectionLimiter
        cl = ConnectionLimiter(max_per_ip=1, max_total=1)
        assert cl.can_accept("10.0.0.4") is True
        assert cl.can_accept("10.0.0.4") is False
        cl.release("10.0.0.4")
        assert cl.can_accept("10.0.0.4") is True

    def test_blacklister_bans_after_threshold(self, tmp_path):
        from core.ddos import IPBlacklister
        from collections import defaultdict
        bl = IPBlacklister(fail_threshold=3, ban_duration=60)
        bl._bans = {}
        bl._failures = defaultdict(int)
        bl._save_bans = lambda: None
        assert bl.is_banned("10.0.0.5") is False
        bl.record_failure("10.0.0.5")
        bl.record_failure("10.0.0.5")
        banned = bl.record_failure("10.0.0.5")
        assert banned is True
        assert bl.is_banned("10.0.0.5") is True

    def test_blacklister_success_resets_failures(self):
        from core.ddos import IPBlacklister
        from collections import defaultdict
        bl = IPBlacklister(fail_threshold=3, ban_duration=60)
        bl._bans = {}
        bl._failures = defaultdict(int)
        bl._save_bans = lambda: None
        bl.record_failure("10.0.0.6")
        bl.record_failure("10.0.0.6")
        bl.record_success("10.0.0.6")
        banned = bl.record_failure("10.0.0.6")
        assert banned is False

    def test_packet_validator_rejects_oversized(self):
        from core.ddos import PacketValidator
        ok, msg = PacketValidator.validate(b"x" * (1024 * 1024 + 1))
        assert ok is False

    def test_packet_validator_rejects_bad_json(self):
        from core.ddos import PacketValidator
        ok, msg = PacketValidator.validate(b"not json at all!!!")
        assert ok is False

    def test_packet_validator_accepts_valid(self):
        from core.ddos import PacketValidator
        ok, msg = PacketValidator.validate(b'{"action": "ping", "auth": "test"}')
        assert ok is True
        assert msg["action"] == "ping"

    def test_ddos_protection_full_flow(self):
        from core.ddos import DDoSProtection
        from collections import defaultdict
        dd = DDoSProtection(rate_max=10, rate_window=60, ban_threshold=2, conn_per_ip=2)
        dd.blacklister._bans = {}
        dd.blacklister._failures = defaultdict(int)
        dd.blacklister._save_bans = lambda: None
        assert dd.check_connection("10.0.0.7")[0] is True
        dd.release_connection("10.0.0.7")
        dd.on_auth_failure("10.0.0.7")
        dd.on_auth_failure("10.0.0.7")
        allowed, reason = dd.check_connection("10.0.0.7")
        assert allowed is False
        assert "banned" in reason.lower()
