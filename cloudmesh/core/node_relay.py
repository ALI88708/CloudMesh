"""Controller-side relay profiles, node sidecars, and relay transport.

The relay itself lives in :mod:`cloudmesh.node.cloudmesh_relay` and is shared
with the agent. This module is controller-only: it stores which relays this
controller trusts, which nodes are reachable through them, and opens the
pinned outer TLS + inner TLS transport used by ``NodeClient``.
"""

import hmac
import json
import os
import re
import secrets
import ssl
import time
from pathlib import Path

try:
    from cloudmesh.core.storage import resolve_base_dir
    from cloudmesh.node import cloudmesh_relay as relay
except ImportError:  # `cd cloudmesh && pytest tests` without installed package
    from node import cloudmesh_relay as relay

    from core.storage import resolve_base_dir

RELAY_PROFILES_FILE = ".relays.json"
NODE_RELAY_FILE = ".node_relay.json"
DEFAULT_POOL = 4

RelayError = relay.RelayError

_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def split_relay_url(url):
    """Split ``host:port`` or ``[v6]:port`` into a host and an integer port."""
    if not isinstance(url, str):
        raise RelayError("relay URL must be host:port")
    text = url.strip()
    if not text:
        raise RelayError("relay URL must be host:port")
    if text.startswith("["):
        end = text.find("]")
        if end == -1:
            raise RelayError("relay URL must be host:port")
        host = text[1:end]
        rest = text[end + 1 :]
        if not rest.startswith(":") or len(rest) < 2:
            raise RelayError("relay URL must be host:port")
        port_text = rest[1:]
    else:
        host, separator, port_text = text.rpartition(":")
        if not separator or not host or ":" in host:
            raise RelayError("relay URL must be host:port")
    if not port_text.isdigit():
        raise RelayError("relay URL must be host:port")
    port = int(port_text)
    if not 1 <= port <= 65535:
        raise RelayError("relay URL must be host:port")
    return host, port


def _atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
    )
    os.replace(temporary, path)
    if os.name != "nt":
        try:
            path.chmod(0o600)
        except OSError:
            pass


class _JsonStore:
    filename = ""

    def __init__(self, base_dir=None):
        base = Path(base_dir) if base_dir is not None else resolve_base_dir()
        self.path = base / self.filename
        self.last_error = None

    def load(self):
        self.last_error = None
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.last_error = f"{self.filename} is corrupt: {exc}"
            return {}
        if not isinstance(data, dict):
            self.last_error = f"{self.filename} is corrupt: expected an object"
            return {}
        return {
            key: value for key, value in data.items() if isinstance(value, dict)
        }

    def remove(self, key):
        data = self.load()
        if key not in data:
            return False
        del data[key]
        _atomic_write(self.path, data)
        return True


class RelayProfileStore(_JsonStore):
    """Trusted relays: ``{url: {admin_key, relay_fingerprint, ca_file}}``."""

    filename = RELAY_PROFILES_FILE

    def get(self, url):
        return self.load().get(url)

    def set(self, url, admin_key, relay_fingerprint, ca_file=None):
        split_relay_url(url)
        if not isinstance(admin_key, str) or not _HEX64.fullmatch(admin_key):
            raise RelayError("relay admin key must be 64 hex characters")
        if not isinstance(relay_fingerprint, str) or not _HEX64.fullmatch(
            relay_fingerprint
        ):
            raise RelayError("relay fingerprint must be 64 hex characters")
        data = self.load()
        if self.last_error:
            raise RelayError(self.last_error)
        data[url] = {
            "admin_key": admin_key,
            "relay_fingerprint": relay_fingerprint,
            "ca_file": ca_file,
        }
        _atomic_write(self.path, data)


class NodeRelayStore(_JsonStore):
    """Controller view of nodes reachable through a relay, keyed by node name."""

    filename = NODE_RELAY_FILE

    def get(self, name):
        return self.load().get(name)

    def set(self, name, entry):
        if not isinstance(name, str):
            raise TypeError("node name must be a string")
        if not name:
            raise ValueError("node name must be non-empty")
        if not isinstance(entry, dict):
            raise TypeError("node relay entry must be an object")
        data = self.load()
        if self.last_error:
            raise RelayError(self.last_error)
        data[name] = entry
        _atomic_write(self.path, data)

    def remove(self, name):
        return super().remove(name)

    def names(self):
        return set(self.load())


def _close_quietly(sock):
    try:
        sock.close()
    except OSError:
        pass


class RelayAdminClient:
    """Enroll, revoke, and query a relay over pinned outer TLS."""

    def __init__(self, url, admin_key, relay_fingerprint, ca_file=None, timeout=10.0):
        self.url = url
        self.host, self.port = split_relay_url(url)
        if not admin_key:
            raise RelayError("relay admin key is required")
        if not relay_fingerprint:
            raise RelayError("relay fingerprint is required")
        self.admin_key = admin_key
        self.relay_fingerprint = relay_fingerprint
        self.ca_file = ca_file
        self.timeout = timeout

    def _request(self, action, relay_id="", **extra):
        ts = int(time.time())
        nonce = secrets.token_hex(8)
        payload = {
            "type": "admin",
            "action": action,
            "relay_id": relay_id,
            "ts": ts,
            "nonce": nonce,
            "mac": relay.admin_mac(
                self.admin_key, action, relay_id, ts, nonce
            ),
        }
        payload.update(extra)
        sock = relay.open_outer_tls(
            self.host,
            self.port,
            self.relay_fingerprint,
            ca_file=self.ca_file,
            timeout=self.timeout,
        )
        try:
            relay.send_frame(sock, payload)
            reply = relay.recv_frame(sock)
        except (ssl.SSLError, OSError) as exc:
            raise RelayError(f"relay unreachable: {exc}") from exc
        finally:
            _close_quietly(sock)
        if reply is None:
            raise RelayError("relay unreachable: the relay closed the connection")
        if reply.get("type") == "error":
            raise RelayError(
                f"relay rejected the request: {reply.get('message', 'unknown error')}"
            )
        return reply

    def enroll(self, relay_id, token, pool=DEFAULT_POOL):
        return self._request("enroll", relay_id, token=token, pool=pool)

    def revoke(self, relay_id):
        return self._request("revoke", relay_id)

    def status(self):
        return self._request("status")

    def ping(self):
        return self._request("ping")


class RelayTransport:
    """Pair through a relay, verify the node, and return the inner TLS socket."""

    def __init__(self, entry, profile, client_id, timeout=10.0):
        if not isinstance(entry, dict) or not isinstance(profile, dict):
            raise RelayError("relay transport needs entry and profile objects")
        self.relay_id = str(entry.get("relay_id", ""))
        self.url = str(entry.get("url", ""))
        self.relay_fingerprint = str(entry.get("relay_fingerprint", ""))
        self.node_fingerprint = str(entry.get("node_fingerprint", ""))
        self.admin_key = str(profile.get("admin_key", ""))
        self.ca_file = profile.get("ca_file")
        self.client_id = str(client_id)
        self.timeout = timeout
        split_relay_url(self.url)
        for label, value in (
            ("relay_id", self.relay_id),
            ("client_id", self.client_id),
        ):
            if _HEX32.fullmatch(value) is None:
                raise RelayError(f"relay transport needs a 32 hex {label}")
        for label, value in (
            ("relay fingerprint", self.relay_fingerprint),
            ("node fingerprint", self.node_fingerprint),
            ("admin key", self.admin_key),
        ):
            if _HEX64.fullmatch(value) is None:
                raise RelayError(f"relay transport needs a 64 hex {label}")

    def connect(self):
        host, port = split_relay_url(self.url)
        sock = relay.open_outer_tls(
            host,
            port,
            self.relay_fingerprint,
            ca_file=self.ca_file,
            timeout=self.timeout,
        )
        try:
            ts = int(time.time())
            nonce = secrets.token_hex(8)
            relay.send_frame(
                sock,
                {
                    "type": "connect",
                    "relay_id": self.relay_id,
                    "client_id": self.client_id,
                    "ts": ts,
                    "nonce": nonce,
                    "mac": relay.connect_mac(
                        self.admin_key,
                        self.relay_id,
                        self.client_id,
                        ts,
                        nonce,
                    ),
                },
            )
            reply = relay.recv_frame(sock)
        except (ssl.SSLError, OSError) as exc:
            _close_quietly(sock)
            raise RelayError(f"relay pairing failed: {exc}") from exc
        if not reply or reply.get("type") != "paired":
            message = (reply or {}).get("message", "the relay closed the connection")
            _close_quietly(sock)
            raise RelayError(f"relay pairing failed: {message}")
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            inner = relay.wrap_inner_tls(
                sock,
                context,
                server_side=False,
                server_hostname=self.relay_id,
                timeout=self.timeout,
            )
        except (relay.RelayError, ssl.SSLError, OSError) as exc:
            _close_quietly(sock)
            raise RelayError(f"relay inner TLS failed: {exc}") from exc
        try:
            peer = inner.getpeercert(binary_form=True)
        except (ssl.SSLError, OSError) as exc:
            inner.close()
            raise RelayError(f"relay inner TLS failed: {exc}") from exc
        if not peer or not hmac.compare_digest(
            relay.der_fingerprint(peer), self.node_fingerprint
        ):
            inner.close()
            raise RelayError("relay node identity mismatch")
        return inner
