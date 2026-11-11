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
import tempfile
import time
from pathlib import Path
from typing import Protocol

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


NODE_RELAY_DIR = "~/.cloudmesh-node"

_RESTART_CANDIDATES = (
    ("command -v systemctl", "systemctl restart cloudmesh-node"),
    ("command -v service", "service cloudmesh-node restart"),
    (
        "test -x /usr/local/etc/rc.d/cloudmesh_node",
        "/usr/local/etc/rc.d/cloudmesh_node restart",
    ),
    ("test -x /etc/rc.d/cloudmesh_node", "/etc/rc.d/cloudmesh_node restart"),
    ("test -x ~/.cloudmesh-node/restart.sh", "~/.cloudmesh-node/restart.sh"),
)


class SSHRunner(Protocol):
    """Minimal command/upload surface used by the relay provisioner."""

    def run(self, host, user, key, command, port=22, timeout=30):
        """Run ``command`` and return ``(output, exit_status)``."""

    def upload_bytes(self, host, user, key, remote_path, data, mode=0o600, port=22):
        """Write ``data`` to ``remote_path`` with ``mode`` permissions."""


class ParamikoSSHRunner:
    """Run commands and upload files over SSH with host-key verification."""

    def __init__(self, known_hosts=None):
        self.known_hosts = known_hosts

    def _connect(self, host, user, key, port):
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        known = (
            Path(self.known_hosts)
            if self.known_hosts
            else Path.home() / ".ssh" / "known_hosts"
        )
        if known.exists():
            client.load_host_keys(str(known))
        try:
            client.connect(
                hostname=host,
                port=port,
                username=user,
                key_filename=key,
                timeout=10,
            )
        except (paramiko.SSHException, OSError) as exc:
            client.close()
            raise RelayError(f"ssh connection failed: {exc}") from exc
        return client

    def run(self, host, user, key, command, port=22, timeout=30):
        import paramiko

        client = self._connect(host, user, key, port)
        try:
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            output = (stdout.read() + stderr.read()).decode("utf-8", "replace")
            return output, stdout.channel.recv_exit_status()
        except (paramiko.SSHException, OSError) as exc:
            raise RelayError(f"ssh command failed: {exc}") from exc
        finally:
            client.close()

    def upload_bytes(self, host, user, key, remote_path, data, mode=0o600, port=22):
        import io

        import paramiko

        client = self._connect(host, user, key, port)
        try:
            sftp = client.open_sftp()
            try:
                if remote_path.startswith("~/"):
                    remote_path = sftp.normalize(".").rstrip("/") + remote_path[1:]
                sftp.putfo(io.BytesIO(data), remote_path)
                try:
                    sftp.chmod(remote_path, mode)
                except OSError:
                    pass
            finally:
                sftp.close()
        except (paramiko.SSHException, OSError) as exc:
            raise RelayError(f"ssh upload failed: {exc}") from exc
        finally:
            client.close()


def restart_agent(runner, host, user, key, port=22):
    """Restart the node agent through the first service manager that works."""
    for probe, command in _RESTART_CANDIDATES:
        try:
            _, status = runner.run(host, user, key, probe, port=port)
        except RelayError:
            continue
        if status != 0:
            continue
        try:
            _, status = runner.run(host, user, key, command, port=port)
        except RelayError:
            continue
        if status == 0:
            return True, command
    tried = ", ".join(command for _, command in _RESTART_CANDIDATES)
    return (
        False,
        f"no service manager found; tried {tried}; run ~/.cloudmesh-node/start.sh",
    )


class RelayProvisioner:
    """Prepare a node's relay sidecar, over SSH or on this machine."""

    def __init__(
        self,
        profiles,
        nodes,
        ssh=None,
        base_dir=None,
        admin_client_factory=RelayAdminClient,
    ):
        self.profiles = profiles
        self.nodes = nodes
        self.ssh = ssh if ssh is not None else ParamikoSSHRunner()
        self.base_dir = Path(base_dir) if base_dir is not None else Path.home()
        self.admin_client_factory = admin_client_factory

    @property
    def node_dir(self):
        return self.base_dir / ".cloudmesh-node"

    def _profile(self, url):
        profile = self.profiles.get(url)
        if not profile:
            raise RelayError("relay profile not found")
        return profile

    def _admin(self, url, profile):
        return self.admin_client_factory(
            url,
            profile.get("admin_key"),
            profile.get("relay_fingerprint"),
            ca_file=profile.get("ca_file"),
        )

    @staticmethod
    def _generate_cert(name, directory):
        directory.mkdir(parents=True, exist_ok=True)
        cert_path = directory / "relay-cert.pem"
        key_path = directory / "relay-key.pem"
        fingerprint = relay.generate_self_signed_cert(cert_path, key_path, name)
        return fingerprint, cert_path.read_bytes(), key_path.read_bytes()

    @staticmethod
    def _supplied_cert(cert, key):
        cert_path = Path(cert)
        key_path = Path(key)
        if not cert_path.is_file() or not key_path.is_file():
            raise RelayError("relay certificate or key not found")
        return (
            relay.cert_fingerprint(cert_path),
            cert_path.read_bytes(),
            key_path.read_bytes(),
        )

    @staticmethod
    def _node_config(relay_id, url, token, relay_fingerprint, pool):
        return {
            "relay_id": relay_id,
            "url": url,
            "node_token": token,
            "relay_fingerprint": relay_fingerprint,
            "tls_cert": "relay-cert.pem",
            "tls_key": "relay-key.pem",
            "pool": pool,
        }

    @staticmethod
    def _pool(value):
        try:
            pool = int(value)
        except (TypeError, ValueError) as exc:
            raise RelayError("relay pool must be an integer") from exc
        if not 1 <= pool <= 32:
            raise RelayError("relay pool must be between 1 and 32")
        return pool

    def _remove_remote(self, host, user, key, port, paths):
        if not paths:
            return
        try:
            self.ssh.run(host, user, key, "rm -f " + " ".join(paths), port=port)
        except RelayError:
            pass

    @staticmethod
    def _verified(verify, name, entry, timeout, retry_interval):
        deadline = time.monotonic() + max(0.0, float(timeout))
        while True:
            try:
                if verify(name, entry):
                    return True
            except Exception:  # noqa: BLE001, S110 - probe failures mean "not yet"
                pass
            if time.monotonic() >= deadline:
                return False
            time.sleep(max(0.0, float(retry_interval)))

    def enable_ssh(
        self,
        name,
        url,
        *,
        ssh_host,
        ssh_user,
        ssh_key=None,
        ssh_port=22,
        pool=DEFAULT_POOL,
        cert=None,
        key=None,
        verify=None,
        timeout=15.0,
        retry_interval=0.5,
    ):
        """Install the node relay config over SSH and enroll the node."""
        if bool(cert) != bool(key):
            raise RelayError("both cert and key must be supplied together")
        pool = self._pool(pool)
        profile = self._profile(url)
        relay_id = secrets.token_hex(16)
        token = secrets.token_hex(32)
        if cert:
            node_fingerprint, cert_bytes, key_bytes = self._supplied_cert(cert, key)
        else:
            with tempfile.TemporaryDirectory() as directory:
                node_fingerprint, cert_bytes, key_bytes = self._generate_cert(
                    name, Path(directory)
                )

        config = self._node_config(
            relay_id, url, token, profile["relay_fingerprint"], pool
        )
        uploads = (
            (f"{NODE_RELAY_DIR}/relay-cert.pem", cert_bytes, 0o600),
            (f"{NODE_RELAY_DIR}/relay-key.pem", key_bytes, 0o600),
            (
                f"{NODE_RELAY_DIR}/.node_relay.json",
                json.dumps(config, indent=2).encode("utf-8"),
                0o600,
            ),
        )
        entry = {
            "relay_id": relay_id,
            "url": url,
            "relay_fingerprint": profile["relay_fingerprint"],
            "node_fingerprint": node_fingerprint,
        }
        client = self._admin(url, profile)
        uploaded = []
        enrolled = False
        try:
            for remote_path, data, mode in uploads:
                self.ssh.upload_bytes(
                    ssh_host,
                    ssh_user,
                    ssh_key,
                    remote_path,
                    data,
                    mode=mode,
                    port=ssh_port,
                )
                uploaded.append(remote_path)
            client.enroll(relay_id, token, pool=pool)
            enrolled = True
            self.nodes.set(name, entry)
        except (RelayError, OSError) as exc:
            if enrolled:
                try:
                    client.revoke(relay_id)
                except RelayError:
                    pass
            self.nodes.remove(name)
            self._remove_remote(
                ssh_host, ssh_user, ssh_key, ssh_port, uploaded
            )
            raise RelayError(str(exc)) from exc

        restart_ok, restart_detail = restart_agent(
            self.ssh, ssh_host, ssh_user, ssh_key, port=ssh_port
        )
        result = dict(entry)
        result["restart_ok"] = restart_ok
        result["restart_command"] = restart_detail
        if not restart_ok:
            print(f"warning: {restart_detail}")
            return result

        if verify is not None and not self._verified(
            verify, name, entry, timeout, retry_interval
        ):
            try:
                client.revoke(relay_id)
            except RelayError:
                pass
            self.nodes.remove(name)
            self._remove_remote(
                ssh_host,
                ssh_user,
                ssh_key,
                ssh_port,
                [remote_path for remote_path, _, _ in uploads],
            )
            raise RelayError(f"relay verification failed for node {name}")
        return result

    def enable_local(self, name, url, pool=DEFAULT_POOL):
        """Write a node relay config on this machine without contacting the relay."""
        pool = self._pool(pool)
        profile = self._profile(url)
        relay_id = secrets.token_hex(16)
        token = secrets.token_hex(32)
        node_fingerprint, _, _ = self._generate_cert(name, self.node_dir)
        config = self._node_config(
            relay_id, url, token, profile["relay_fingerprint"], pool
        )
        _atomic_write(self.node_dir / ".node_relay.json", config)
        return {
            "relay_id": relay_id,
            "token": token,
            "node_fingerprint": node_fingerprint,
            "relay_fingerprint": profile["relay_fingerprint"],
            "import_command": (
                f"cm node relay import -n {name} --relay {url} "
                f"--relay-id {relay_id} --token {token} "
                f"--node-fingerprint {node_fingerprint} "
                f"--relay-fingerprint {profile['relay_fingerprint']}"
            ),
        }

    def import_local(
        self,
        name,
        url,
        relay_id,
        token,
        node_fingerprint,
        relay_fingerprint,
        pool=DEFAULT_POOL,
    ):
        """Enroll material generated on the node and save the controller sidecar."""
        split_relay_url(url)
        pool = self._pool(pool)
        for label, value, pattern, length in (
            ("relay id", relay_id, _HEX32, 32),
            ("relay token", token, _HEX64, 64),
            ("node fingerprint", node_fingerprint, _HEX64, 64),
            ("relay fingerprint", relay_fingerprint, _HEX64, 64),
        ):
            if not isinstance(value, str) or pattern.fullmatch(value) is None:
                raise RelayError(f"{label} must be {length} hex characters")
        profile = self._profile(url)
        entry = {
            "relay_id": relay_id,
            "url": url,
            "relay_fingerprint": relay_fingerprint,
            "node_fingerprint": node_fingerprint,
        }
        client = self._admin(url, profile)
        client.enroll(relay_id, token, pool=pool)
        try:
            self.nodes.set(name, entry)
        except RelayError:
            try:
                client.revoke(relay_id)
            except RelayError:
                pass
            raise
        return dict(entry)

    def disable_ssh(
        self, name, url, *, ssh_host, ssh_user, ssh_key=None, ssh_port=22
    ):
        """Remove the node relay config over SSH and revoke its token."""
        profile = self._profile(url)
        self._remove_remote(
            ssh_host,
            ssh_user,
            ssh_key,
            ssh_port,
            [
                f"{NODE_RELAY_DIR}/.node_relay.json",
                f"{NODE_RELAY_DIR}/relay-cert.pem",
                f"{NODE_RELAY_DIR}/relay-key.pem",
            ],
        )
        restart_ok, restart_detail = restart_agent(
            self.ssh, ssh_host, ssh_user, ssh_key, port=ssh_port
        )
        entry = self.nodes.get(name) or {}
        relay_id = entry.get("relay_id")
        if relay_id:
            self._admin(url, profile).revoke(relay_id)
        self.nodes.remove(name)
        return {"restart_ok": restart_ok, "restart_command": restart_detail}

    def disable_local(self, name, url):
        """Remove this machine's node relay config and the controller sidecar."""
        try:
            (self.node_dir / ".node_relay.json").unlink()
        except FileNotFoundError:
            pass
        self.nodes.remove(name)
        return {"revoke_command": f"cm relay revoke -n {name} --relay {url}"}
