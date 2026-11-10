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
import tempfile
import threading
import time
from pathlib import Path

MAX_FRAME_BYTES = 64 * 1024
MAX_CLOCK_SKEW = 30

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
