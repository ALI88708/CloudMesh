import secrets
import socket
import ssl
import threading
import time

from cloudmesh.core.node_client import NodeClient
from cloudmesh.core.node_relay import NodeRelayStore, RelayProfileStore
from cloudmesh.node import cloudmesh_relay as relay

RELAY_ID = "ab" * 16
TOKEN = "cd" * 32
ADMIN_KEY = "11" * 32


def wait_for(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class RelayHandle:
    def __init__(self, server):
        self.server = server
        self.profile = {
            "admin_key": server.admin_key,
            "relay_fingerprint": server.fingerprint,
            "ca_file": None,
        }

    @property
    def address(self):
        return self.server.address

    def stop(self):
        self.server.stop()


class FakeNode:
    """A parked node that speaks inner TLS and answers execute requests."""

    def __init__(
        self,
        relay_address,
        node_cert,
        node_key,
        relay_fingerprint,
        node_fingerprint,
        timeout=5.0,
    ):
        self.relay_address = relay_address
        self.node_cert = node_cert
        self.node_key = node_key
        self.relay_fingerprint = relay_fingerprint
        self.node_fingerprint = node_fingerprint
        self.received_frames = 0
        self._sock = None
        self._inner = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def entry(self):
        return {
            "relay_id": RELAY_ID,
            "url": f"127.0.0.1:{self.relay_address[1]}",
            "relay_fingerprint": self.relay_fingerprint,
            "node_fingerprint": self.node_fingerprint,
        }

    def _run(self):
        try:
            raw = socket.create_connection(self.relay_address, timeout=5)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self._sock = context.wrap_socket(raw, server_hostname="relay.test")
            ts = int(time.time())
            nonce = secrets.token_hex(8)
            relay.send_frame(
                self._sock,
                {
                    "type": "register",
                    "relay_id": RELAY_ID,
                    "ts": ts,
                    "nonce": nonce,
                    "mac": relay.register_mac(TOKEN, RELAY_ID, ts, nonce),
                },
            )
            if (relay.recv_frame(self._sock) or {}).get("type") != "parked":
                return
            if (relay.recv_frame(self._sock) or {}).get("type") != "paired":
                return
            inner_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            inner_context.load_cert_chain(self.node_cert, self.node_key)
            self._inner = relay.wrap_inner_tls(
                self._sock, inner_context, server_side=True, timeout=5
            )
            request = relay.recv_frame(self._inner)
            if request is None:
                return
            self.received_frames += 1
            relay.send_frame(
                self._inner,
                {
                    "type": "result",
                    "data": {"stdout": f"ok {request.get('command', '')}".strip()},
                },
            )
        except (OSError, relay.RelayError):
            pass
        finally:
            for item in (self._inner, self._sock):
                if item is not None:
                    try:
                        item.close()
                    except OSError:
                        pass

    def stop(self):
        for item in (self._inner, self._sock):
            if item is not None:
                try:
                    item.close()
                except OSError:
                    pass
        self._thread.join(timeout=5)


def start_fake_relay_and_node(tmp_path, node_fingerprint=None):
    relay_cert, relay_key = tmp_path / "relay-cert.pem", tmp_path / "relay-key.pem"
    relay.generate_self_signed_cert(relay_cert, relay_key, "relay.test")
    registry = relay.TokenRegistry(tmp_path / "tokens.json")
    registry.add(RELAY_ID, TOKEN, pool=2)
    config = relay.RelayConfig(
        bind="127.0.0.1",
        port=0,
        admin_key=ADMIN_KEY,
        tls_cert=str(relay_cert),
        tls_key=str(relay_key),
        tokens_file=str(tmp_path / "tokens.json"),
    )
    server = relay.RelayServer(config, registry=registry, pair_timeout=0.5)
    server.start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    handle = RelayHandle(server)

    node_cert, node_key = tmp_path / "node-cert.pem", tmp_path / "node-key.pem"
    actual_fingerprint = relay.generate_self_signed_cert(
        node_cert, node_key, RELAY_ID
    )
    node = FakeNode(
        server.address,
        node_cert,
        node_key,
        server.fingerprint,
        node_fingerprint or actual_fingerprint,
    )
    assert wait_for(
        lambda: server.stats()["nodes"].get(RELAY_ID, {}).get("parked") == 1
    )
    return handle, node


def test_from_config_without_a_name_stays_direct():
    client = NodeClient.from_config({"host": "127.0.0.1", "port": 1, "key": "k"})
    assert client.transport == "direct"


def test_from_config_with_a_relay_sidecar_selects_relay(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    NodeRelayStore(tmp_path).set(
        "web-1",
        {
            "relay_id": RELAY_ID,
            "url": "relay.test:9997",
            "relay_fingerprint": "cd" * 32,
            "node_fingerprint": "ef" * 32,
        },
    )
    RelayProfileStore(tmp_path).set("relay.test:9997", ADMIN_KEY, "cd" * 32)

    client = NodeClient.from_config(
        {"host": "relay.test", "port": 9997, "key": "k"}, name="web-1"
    )

    assert client.transport == "relay"
    assert client.relay_entry["relay_id"] == RELAY_ID
    assert client.relay_profile["admin_key"] == ADMIN_KEY


def test_from_config_without_a_sidecar_stays_direct(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))

    client = NodeClient.from_config(
        {"host": "relay.test", "port": 9997, "key": "k"}, name="web-1"
    )

    assert client.transport == "direct"


def test_an_incomplete_relay_entry_returns_a_named_error(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    NodeRelayStore(tmp_path).set("web-1", {"relay_id": RELAY_ID})

    client = NodeClient.from_config(
        {"host": "relay.test", "port": 9997, "key": "k"}, name="web-1"
    )
    result = client.ping()

    assert result is False
    assert "relay config is incomplete" in client.last_error.lower()


def test_a_transient_relay_failure_does_not_poison_the_client(tmp_path):
    """One failed pairing must not latch: the next attempt has to work.

    The node re-parks between sessions, so a pairing failure is usually the
    instant between a finished request and the next parked connection. Before
    this was fixed, `last_error` short-circuited every later call, and a relay
    restart left the controller permanently convinced the node was down.
    """
    relay_server, node_server = start_fake_relay_and_node(tmp_path)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        dead_port = probe.getsockname()[1]
    entry = dict(node_server.entry)
    entry["url"] = f"127.0.0.1:{dead_port}"
    client = NodeClient(
        "127.0.0.1",
        relay_server.address[1],
        "auth",
        transport="relay",
        relay_entry=entry,
        relay_profile=relay_server.profile,
    )
    try:
        assert client.execute("uptime").get("message")
        assert client.last_error

        client.relay_entry["url"] = f"127.0.0.1:{relay_server.address[1]}"
        assert client.execute("uptime")["stdout"].startswith("ok")
        assert client.last_error is None
    finally:
        node_server.stop()
        relay_server.stop()


def test_a_missing_relay_profile_returns_a_named_error(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    NodeRelayStore(tmp_path).set(
        "web-1",
        {
            "relay_id": RELAY_ID,
            "url": "relay.test:9997",
            "relay_fingerprint": "cd" * 32,
            "node_fingerprint": "ef" * 32,
        },
    )

    client = NodeClient.from_config(
        {"host": "relay.test", "port": 9997, "key": "k"}, name="web-1"
    )

    assert "relay profile is missing" in client.last_error


def test_relay_execute_round_trip(tmp_path):
    relay_server, node_server = start_fake_relay_and_node(tmp_path)
    client = NodeClient(
        "127.0.0.1",
        relay_server.address[1],
        "auth",
        transport="relay",
        relay_entry=node_server.entry,
        relay_profile=relay_server.profile,
    )
    try:
        assert client.execute("uptime")["stdout"].startswith("ok")
    finally:
        node_server.stop()
        relay_server.stop()


def test_no_application_bytes_are_sent_before_the_node_fingerprint_is_verified(tmp_path):
    relay_server, node_server = start_fake_relay_and_node(
        tmp_path, node_fingerprint="00" * 32
    )
    client = NodeClient(
        "127.0.0.1",
        relay_server.address[1],
        "auth",
        transport="relay",
        relay_entry=node_server.entry,
        relay_profile=relay_server.profile,
    )
    try:
        client.execute("uptime")
        node_server.stop()
        assert "identity mismatch" in client.last_error.lower()
        assert node_server.received_frames == 0
    finally:
        node_server.stop()
        relay_server.stop()
