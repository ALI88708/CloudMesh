"""Relay protocol primitives shared by the relay, the node agent, and the controller.

The agent loads this module next to ``cloudmesh_node.py``, so it uses only the
standard library at import time. Certificate helpers import ``cryptography``
inside the function.
"""

import hashlib
import hmac
import json
import os
import re
import socket
import ssl
import tempfile
import threading
import time
from pathlib import Path

MAX_FRAME_BYTES = 64 * 1024
MAX_CLOCK_SKEW = 30
DEFAULT_RELAY_PORT = 9997
PAIR_TIMEOUT_SECONDS = 5.0
KEEPALIVE_SECONDS = 30.0
PONG_TIMEOUT_SECONDS = 5.0
CAPTURE_LIMIT_BYTES = 8 * 1024 * 1024

_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX_NONCE = re.compile(r"^(?:[0-9a-f]{2}){8,32}$")


class RelayError(Exception):
    """A relay protocol, configuration, or transport failure."""


def _read_exact(sock, length):
    chunks = []
    remaining = length
    while remaining:
        try:
            chunk = sock.recv(remaining)
        except OSError:
            return None
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def encode_frame(payload):
    body = json.dumps(payload).encode("utf-8")
    return len(body).to_bytes(4, "big") + body


def recv_frame(sock, max_bytes=MAX_FRAME_BYTES):
    header = _read_exact(sock, 4)
    if header is None:
        return None
    length = int.from_bytes(header, "big")
    if length <= 0 or length > max_bytes:
        return None
    body = _read_exact(sock, length)
    if body is None:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def send_frame(sock, payload):
    sock.sendall(encode_frame(payload))


def _mac(key, message):
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def register_mac(token, relay_id, ts, nonce):
    return _mac(token, f"register|{relay_id}|{ts}|{nonce}")


def connect_mac(admin_key, relay_id, client_id, ts, nonce):
    return _mac(admin_key, f"connect|{relay_id}|{client_id}|{ts}|{nonce}")


def admin_mac(admin_key, action, relay_id, ts, nonce):
    return _mac(admin_key, f"admin|{action}|{relay_id}|{ts}|{nonce}")


def verify_mac(expected, supplied):
    if not isinstance(expected, str) or not isinstance(supplied, str):
        return False
    return hmac.compare_digest(expected, supplied)


def _is_hex(value, pattern):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _normalise_relay_id(relay_id):
    if not _is_hex(relay_id, _HEX32):
        raise ValueError("relay_id must be 32 hex characters")
    return relay_id


def _normalise_token(token):
    if not _is_hex(token, _HEX64):
        raise ValueError("token must be 64 hex characters")
    return token


class NonceCache:
    """Bounded replay cache for handshake nonces, per spec section 9.3."""

    def __init__(self, ttl=60, capacity=10000):
        self.ttl = ttl
        self.capacity = capacity
        self._seen = {}
        self._lock = threading.Lock()

    def _evict(self, now):
        expired = [key for key, seen_at in self._seen.items() if now - seen_at > self.ttl]
        for key in expired:
            del self._seen[key]

    def accept(self, scope, nonce, ts, now=None):
        if not _is_hex(nonce, _HEX_NONCE):
            return False, "malformed nonce"
        now = time.time() if now is None else now
        try:
            if abs(now - ts) > MAX_CLOCK_SKEW:
                return False, "stale timestamp"
        except TypeError:
            return False, "stale timestamp"
        key = (scope, nonce)
        with self._lock:
            self._evict(now)
            if key in self._seen:
                return False, "replayed nonce"
            if len(self._seen) >= self.capacity:
                oldest = min(self._seen, key=lambda item: self._seen[item])
                del self._seen[oldest]
            self._seen[key] = now
        return True, ""


def _atomic_write(path, data, mode=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
        if mode is not None and os.name != "nt":
            path.chmod(mode)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


class TokenRegistry:
    """Node token registry stored as ``{relay_id: {token, pool, created_at}}``."""

    def __init__(self, path):
        self.path = Path(path)
        self.last_error = None
        self._lock = threading.Lock()

    def load(self):
        self.last_error = None
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.last_error = f"token registry is corrupt: {exc}"
            return {}
        if not isinstance(data, dict):
            self.last_error = "token registry is corrupt: expected an object"
            return {}
        return data

    def add(self, relay_id, token, pool=4):
        _normalise_relay_id(relay_id)
        _normalise_token(token)
        if isinstance(pool, bool) or not isinstance(pool, int) or not 1 <= pool <= 32:
            raise ValueError("pool must be an integer between 1 and 32")
        with self._lock:
            data = self.load()
            if self.last_error:
                raise RelayError(self.last_error)
            data[relay_id] = {
                "token": token,
                "pool": pool,
                "created_at": int(time.time()),
            }
            self._write(data)

    def remove(self, relay_id):
        _normalise_relay_id(relay_id)
        with self._lock:
            data = self.load()
            if self.last_error:
                raise RelayError(self.last_error)
            if relay_id not in data:
                return False
            del data[relay_id]
            self._write(data)
            return True

    def verify(self, relay_id, token):
        if not _is_hex(relay_id, _HEX32) or not isinstance(token, str):
            return False
        entry = self.load().get(relay_id) or {}
        return hmac.compare_digest(str(entry.get("token", "")), token)

    def pool_for(self, relay_id):
        if not _is_hex(relay_id, _HEX32):
            return 0
        entry = self.load().get(relay_id) or {}
        pool = entry.get("pool")
        return pool if isinstance(pool, int) else 0

    def count(self):
        return len(self.load())

    def _write(self, data):
        _atomic_write(
            self.path,
            json.dumps(data, indent=2, sort_keys=True).encode("utf-8"),
            0o600,
        )


def der_fingerprint(der):
    return hashlib.sha256(der).hexdigest()


def cert_fingerprint(cert_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    certificate = x509.load_pem_x509_certificate(Path(cert_path).read_bytes())
    return der_fingerprint(certificate.public_bytes(serialization.Encoding.DER))


def generate_self_signed_cert(cert_path, key_path, common_name, days=3650):
    from datetime import datetime, timedelta, timezone

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False
        )
        .sign(key, hashes.SHA256())
    )

    key_bytes = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    cert_bytes = certificate.public_bytes(serialization.Encoding.PEM)
    _atomic_write(key_path, key_bytes, 0o600)
    _atomic_write(cert_path, cert_bytes, 0o644)
    return der_fingerprint(certificate.public_bytes(serialization.Encoding.DER))

class RelayConfig:
    """Relay server settings stored beside the certificate and token files."""

    FIELDS = ("bind", "port", "admin_key", "tls_cert", "tls_key", "tokens_file")

    def __init__(self, bind, port, admin_key, tls_cert, tls_key, tokens_file):
        self.bind = bind
        self.port = int(port)
        self.admin_key = admin_key
        self.tls_cert = tls_cert
        self.tls_key = tls_key
        self.tokens_file = tokens_file

    @classmethod
    def load(cls, path):
        path = Path(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RelayError(f"relay config is corrupt: {exc}") from exc
        if not isinstance(raw, dict):
            raise RelayError("relay config is corrupt: expected an object")
        missing = [name for name in cls.FIELDS if name not in raw]
        if missing:
            raise RelayError(
                f"relay config is corrupt: missing {', '.join(missing)}"
            )
        base = path.parent

        def resolve(value):
            candidate = Path(value)
            return str(candidate if candidate.is_absolute() else base / candidate)

        return cls(
            bind=raw["bind"],
            port=raw["port"],
            admin_key=raw["admin_key"],
            tls_cert=resolve(raw["tls_cert"]),
            tls_key=resolve(raw["tls_key"]),
            tokens_file=resolve(raw["tokens_file"]),
        )

    def save(self, path):
        raw = {
            "bind": self.bind,
            "port": self.port,
            "admin_key": self.admin_key,
            "tls_cert": self.tls_cert,
            "tls_key": self.tls_key,
            "tokens_file": self.tokens_file,
        }
        _atomic_write(Path(path), json.dumps(raw, indent=2).encode("utf-8"), 0o600)


class _HandshakeLimiter:
    """Per-IP handshake rate, concurrency, and auth-failure ban."""

    def __init__(
        self,
        attempts=60,
        window=60,
        concurrent=20,
        failures=10,
        ban_seconds=300,
    ):
        self.attempts = attempts
        self.window = window
        self.concurrent = concurrent
        self.failures = failures
        self.ban_seconds = ban_seconds
        self._lock = threading.Lock()
        self._events = {}
        self._active = {}
        self._failures = {}
        self._bans = {}

    def check(self, ip):
        now = time.monotonic()
        with self._lock:
            until = self._bans.get(ip, 0)
            if until:
                if now < until:
                    return False
                del self._bans[ip]
            events = [stamp for stamp in self._events.get(ip, []) if now - stamp <= self.window]
            events.append(now)
            self._events[ip] = events
            if len(events) > self.attempts:
                return False
            if self._active.get(ip, 0) >= self.concurrent:
                return False
            self._active[ip] = self._active.get(ip, 0) + 1
            return True

    def release(self, ip):
        with self._lock:
            self._active[ip] = max(0, self._active.get(ip, 1) - 1)

    def on_failure(self, ip):
        with self._lock:
            count = self._failures.get(ip, 0) + 1
            self._failures[ip] = count
            if count >= self.failures:
                self._bans[ip] = time.monotonic() + self.ban_seconds
                self._failures[ip] = 0


class ParkedConnection:
    """A registered node connection waiting for a controller."""

    def __init__(self, sock, relay_id):
        self.sock = sock
        self.relay_id = relay_id
        self.client_id = None
        self.paired = threading.Event()
        self.closed = threading.Event()
        self.lock = threading.Lock()

    def claim(self, client_id):
        with self.lock:
            if self.paired.is_set() or self.closed.is_set():
                return False
            self.client_id = client_id
            try:
                send_frame(self.sock, {"type": "paired", "client_id": client_id})
            except OSError:
                return False
            self.paired.set()
            return True

    def wait(self):
        self.sock.settimeout(1.0)
        next_ping = time.monotonic() + KEEPALIVE_SECONDS
        while not self.paired.is_set():
            if self.closed.is_set():
                return False
            if time.monotonic() < next_ping:
                time.sleep(0.02)
                continue
            with self.lock:
                if self.paired.is_set():
                    return True
                try:
                    send_frame(self.sock, {"type": "ping"})
                    self.sock.settimeout(PONG_TIMEOUT_SECONDS)
                    response = recv_frame(self.sock)
                except OSError:
                    return False
            if not response or response.get("type") != "pong":
                return False
            self.sock.settimeout(1.0)
            next_ping = time.monotonic() + KEEPALIVE_SECONDS
        return True

    def close(self):
        self.closed.set()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class ParkingRegistry:
    """Per-relay-ID FIFO of parked connections and paired counts."""

    def __init__(self):
        self._lock = threading.Lock()
        self._parked = {}
        self._paired = {}

    def park(self, conn, limit):
        with self._lock:
            live = [
                item
                for item in self._parked.get(conn.relay_id, [])
                if not item.closed.is_set()
            ]
            self._parked[conn.relay_id] = live
            if len(live) >= limit:
                return False
            live.append(conn)
            return True

    def unpark(self, conn):
        with self._lock:
            conns = self._parked.get(conn.relay_id, [])
            if conn in conns:
                conns.remove(conn)

    def take(self, relay_id, timeout):
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                conns = self._parked.get(relay_id, [])
                while conns and conns[0].closed.is_set():
                    conns.pop(0)
                if conns:
                    return conns.pop(0)
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.01)

    def close_all(self, relay_id):
        with self._lock:
            conns = list(self._parked.get(relay_id, []))
            self._parked[relay_id] = []
        for conn in conns:
            conn.close()

    def close_everything(self):
        with self._lock:
            relay_ids = list(self._parked)
        for relay_id in relay_ids:
            self.close_all(relay_id)

    def mark_paired(self, relay_id):
        with self._lock:
            self._paired[relay_id] = self._paired.get(relay_id, 0) + 1

    def mark_unpaired(self, relay_id):
        with self._lock:
            self._paired[relay_id] = max(0, self._paired.get(relay_id, 0) - 1)

    def counts(self):
        with self._lock:
            relay_ids = set(self._parked) | set(self._paired)
            return {
                relay_id: {
                    "parked": sum(
                        1
                        for item in self._parked.get(relay_id, [])
                        if not item.closed.is_set()
                    ),
                    "paired": self._paired.get(relay_id, 0),
                }
                for relay_id in relay_ids
            }


class RelayServer:
    """Outbound-only pairing server: nodes park, controllers pair, bytes flow."""

    def __init__(
        self,
        config,
        registry=None,
        pair_timeout=PAIR_TIMEOUT_SECONDS,
        capture=False,
    ):
        self.config = config
        self.registry = registry if registry is not None else TokenRegistry(config.tokens_file)
        self.registry.load()
        if self.registry.last_error:
            raise RelayError(self.registry.last_error)
        self.pair_timeout = pair_timeout
        self.capture = capture
        self.address = None
        self.admin_key = config.admin_key
        self._stop = threading.Event()
        self._listener = None
        self._parking = ParkingRegistry()
        self._nonces = NonceCache()
        self._limiter = _HandshakeLimiter()
        self._lock = threading.Lock()
        self._counters = {"registrations": 0, "pairs": 0, "auth_failures": 0}
        self._captured = bytearray()
        self._active_sockets = set()
        self._started_at = None
        self._tls_context = self._build_tls_context()

    @property
    def fingerprint(self):
        return cert_fingerprint(self.config.tls_cert)

    def _build_tls_context(self):
        for path in (self.config.tls_cert, self.config.tls_key):
            if not Path(path).is_file():
                raise RelayError(f"relay TLS file not found: {path}")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        try:
            context.load_cert_chain(self.config.tls_cert, self.config.tls_key)
        except (OSError, ssl.SSLError) as exc:
            raise RelayError(f"relay TLS certificate is unusable: {exc}") from exc
        return context

    def start(self):
        if self._listener is not None:
            return self.address
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((self.config.bind, self.config.port))
            listener.listen(64)
        except OSError as exc:
            listener.close()
            raise RelayError(f"relay could not bind: {exc}") from exc
        listener.settimeout(1.0)
        self._listener = listener
        self.address = listener.getsockname()[:2]
        self._started_at = time.monotonic()
        return self.address

    def serve_forever(self):
        listener = self._listener
        while not self._stop.is_set():
            try:
                client, addr = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._serve_client, args=(client, addr), daemon=True
            ).start()

    def stop(self):
        self._stop.set()
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        self._parking.close_everything()
        with self._lock:
            sockets = list(self._active_sockets)
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def stats(self):
        counts = self._parking.counts()
        with self._lock:
            totals = {
                "parked": sum(item["parked"] for item in counts.values()),
                "paired": sum(item["paired"] for item in counts.values()),
            }
            totals.update(self._counters)
            started_at = self._started_at
        uptime = int(time.monotonic() - started_at) if started_at else 0
        return {
            "version": "4.3.0",
            "uptime_seconds": uptime,
            "nodes": counts,
            "totals": totals,
        }

    def captured_bytes(self):
        with self._lock:
            return bytes(self._captured)

    def revoke(self, relay_id):
        try:
            existed = self.registry.remove(relay_id)
        except (RelayError, ValueError):
            existed = False
        self._parking.close_all(relay_id)
        return existed

    def _serve_client(self, client, addr):
        state = {"released": False}
        ip = addr[0]
        handed_off = False
        tls_sock = None
        try:
            if not self._limiter.check(ip):
                return
            client.settimeout(10.0)
            try:
                tls_sock = self._tls_context.wrap_socket(client, server_side=True)
            except (ssl.SSLError, OSError):
                return
            handed_off = self._handle_connection(tls_sock, addr, state)
        except Exception:
            handed_off = False
        finally:
            self._release_once(ip, state)
            if not handed_off:
                target = tls_sock or client
                try:
                    target.close()
                except OSError:
                    pass

    def _release_once(self, ip, state):
        if not state["released"]:
            state["released"] = True
            self._limiter.release(ip)

    def _handle_connection(self, sock, addr, state):
        request = recv_frame(sock)
        if request is None:
            self._record_auth_failure(addr)
            return False
        kind = request.get("type")
        if kind == "register":
            return self._handle_register(sock, addr, state, request)
        if kind == "connect":
            return self._handle_connect(sock, addr, state, request)
        if kind == "admin":
            return self._handle_admin(sock, addr, state, request)
        self._reject(sock, "unknown message")
        return False

    def _count(self, name):
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + 1

    def _record_auth_failure(self, addr):
        self._limiter.on_failure(addr[0])
        self._count("auth_failures")

    def _reject(self, sock, message, addr=None, auth=False):
        if auth and addr is not None:
            self._record_auth_failure(addr)
        try:
            send_frame(sock, {"type": "error", "message": message})
        except OSError:
            pass

    def _handle_register(self, sock, addr, state, request):
        relay_id = request.get("relay_id", "")
        ts = request.get("ts", 0)
        nonce = request.get("nonce", "")
        mac = request.get("mac", "")
        if not _is_hex(relay_id, _HEX32):
            self._reject(sock, "unauthorized", addr, auth=True)
            return False
        entry = self.registry.load().get(relay_id)
        if not isinstance(entry, dict):
            self._reject(sock, "unauthorized", addr, auth=True)
            return False
        accepted, _reason = self._nonces.accept("register:" + relay_id, nonce, ts)
        token = str(entry.get("token", ""))
        if (
            not accepted
            or not verify_mac(register_mac(token, relay_id, ts, nonce), mac)
            or not self.registry.verify(relay_id, token)
        ):
            self._reject(sock, "unauthorized", addr, auth=True)
            return False

        self._release_once(addr[0], state)
        connection = ParkedConnection(sock, relay_id)
        if not self._parking.park(connection, self.registry.pool_for(relay_id)):
            self._reject(sock, "too many registrations")
            return False
        try:
            send_frame(sock, {"type": "parked"})
        except OSError:
            self._parking.unpark(connection)
            return False
        self._count("registrations")
        if not connection.wait():
            self._parking.unpark(connection)
            return False
        return True

    def _handle_connect(self, sock, addr, state, request):
        relay_id = request.get("relay_id", "")
        client_id = request.get("client_id", "")
        ts = request.get("ts", 0)
        nonce = request.get("nonce", "")
        mac = request.get("mac", "")
        if not _is_hex(relay_id, _HEX32) or not _is_hex(client_id, _HEX32):
            self._reject(sock, "unauthorized", addr, auth=True)
            return False
        accepted, _reason = self._nonces.accept("connect:" + relay_id, nonce, ts)
        expected = connect_mac(
            self.config.admin_key, relay_id, client_id, ts, nonce
        )
        if not accepted or not verify_mac(expected, mac):
            self._reject(sock, "unauthorized", addr, auth=True)
            return False

        connection = self._parking.take(relay_id, self.pair_timeout)
        if connection is None:
            self._reject(sock, "node offline")
            return False
        if not connection.claim(client_id):
            self._reject(sock, "node offline")
            return False
        try:
            send_frame(sock, {"type": "paired"})
        except OSError:
            connection.close()
            return False

        self._release_once(addr[0], state)
        self._parking.mark_paired(relay_id)
        self._count("pairs")
        try:
            self._pump_pair(connection.sock, sock)
        finally:
            self._parking.mark_unpaired(relay_id)
        return True

    def _handle_admin(self, sock, addr, state, request):
        action = request.get("action", "")
        relay_id = request.get("relay_id", "") or ""
        ts = request.get("ts", 0)
        nonce = request.get("nonce", "")
        mac = request.get("mac", "")
        if action not in ("enroll", "revoke", "status", "ping"):
            self._reject(sock, "unauthorized", addr, auth=True)
            return False
        if action in ("enroll", "revoke") and not _is_hex(relay_id, _HEX32):
            self._reject(sock, "unauthorized", addr, auth=True)
            return False
        accepted, _reason = self._nonces.accept(
            f"admin:{action}:{relay_id}", nonce, ts
        )
        expected = admin_mac(self.config.admin_key, action, relay_id, ts, nonce)
        if not accepted or not verify_mac(expected, mac):
            self._reject(sock, "unauthorized", addr, auth=True)
            return False

        self._release_once(addr[0], state)
        if action == "ping":
            send_frame(sock, {"type": "pong"})
            return False
        if action == "status":
            send_frame(sock, {"type": "status", "data": self.stats()})
            return False
        if action == "enroll":
            try:
                self.registry.add(
                    relay_id,
                    request.get("token", ""),
                    int(request.get("pool", 4)),
                )
            except (RelayError, ValueError) as exc:
                self._reject(sock, str(exc))
                return False
            send_frame(sock, {"type": "admin", "data": {"success": True}})
            return False
        success = self.revoke(relay_id)
        send_frame(sock, {"type": "admin", "data": {"success": success}})
        return False

    def _pump_pair(self, node_sock, controller_sock):
        for sock in (node_sock, controller_sock):
            sock.settimeout(None)
        with self._lock:
            self._active_sockets.add(node_sock)
            self._active_sockets.add(controller_sock)
        threads = [
            threading.Thread(
                target=self._pump, args=(node_sock, controller_sock), daemon=True
            ),
            threading.Thread(
                target=self._pump, args=(controller_sock, node_sock), daemon=True
            ),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(2.0)
        for sock in (node_sock, controller_sock):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
            with self._lock:
                self._active_sockets.discard(sock)

    def _pump(self, source, destination):
        while not self._stop.is_set():
            try:
                chunk = source.recv(65536)
            except OSError:
                break
            if not chunk:
                break
            if self.capture:
                self._record_capture(chunk)
            try:
                destination.sendall(chunk)
            except OSError:
                break
        try:
            destination.shutdown(socket.SHUT_WR)
        except OSError:
            pass

    def _record_capture(self, chunk):
        with self._lock:
            remaining = CAPTURE_LIMIT_BYTES - len(self._captured)
            if remaining > 0:
                self._captured.extend(chunk[:remaining])
