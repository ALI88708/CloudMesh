import os
import threading

import pytest

from cloudmesh.core import node_relay
from cloudmesh.node import cloudmesh_relay as relay

RELAY_ID = "ab" * 16
TOKEN = "cd" * 32
ADMIN_KEY = "11" * 32
CLIENT_ID = "ef" * 16


def start_relay(tmp_path, pair_timeout=0.2):
    cert, key = tmp_path / "relay-cert.pem", tmp_path / "relay-key.pem"
    relay.generate_self_signed_cert(cert, key, "relay.test")
    registry = relay.TokenRegistry(tmp_path / "tokens.json")
    registry.add(RELAY_ID, TOKEN, pool=2)
    config = relay.RelayConfig(
        bind="127.0.0.1",
        port=0,
        admin_key=ADMIN_KEY,
        tls_cert=str(cert),
        tls_key=str(key),
        tokens_file=str(tmp_path / "tokens.json"),
    )
    server = relay.RelayServer(config, registry=registry, pair_timeout=pair_timeout)
    server.start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def make_transport(server, relay_fingerprint=None, node_fingerprint="ee" * 32):
    fingerprint = relay_fingerprint or server.fingerprint
    entry = {
        "relay_id": RELAY_ID,
        "url": f"127.0.0.1:{server.address[1]}",
        "relay_fingerprint": fingerprint,
        "node_fingerprint": node_fingerprint,
    }
    profile = {
        "admin_key": server.admin_key,
        "relay_fingerprint": fingerprint,
        "ca_file": None,
    }
    return node_relay.RelayTransport(entry, profile, CLIENT_ID, timeout=5)


def test_profile_store_round_trip(tmp_path):
    store = node_relay.RelayProfileStore(tmp_path)
    store.set("relay.test:9997", "ab" * 32, "cd" * 32)

    assert store.get("relay.test:9997")["admin_key"] == "ab" * 32
    assert store.get("relay.test:9997")["relay_fingerprint"] == "cd" * 32
    assert store.get("missing.test:9997") is None
    if os.name != "nt":
        assert (tmp_path / ".relays.json").stat().st_mode & 0o777 == 0o600


def test_profile_store_remove_does_not_create_the_file(tmp_path):
    store = node_relay.RelayProfileStore(tmp_path)

    assert store.remove("relay.test:9997") is False
    assert not (tmp_path / ".relays.json").exists()


def test_corrupt_profile_store_is_a_named_error(tmp_path):
    (tmp_path / ".relays.json").write_text("{not json", encoding="utf-8")
    store = node_relay.RelayProfileStore(tmp_path)

    assert store.load() == {}
    assert "corrupt" in store.last_error.lower()
    with pytest.raises(node_relay.RelayError):
        store.set("relay.test:9997", "ab" * 32, "cd" * 32)


def test_node_store_round_trip(tmp_path):
    store = node_relay.NodeRelayStore(tmp_path)
    entry = {
        "relay_id": RELAY_ID,
        "url": "relay.test:9997",
        "relay_fingerprint": "cd" * 32,
        "node_fingerprint": "ef" * 32,
    }
    store.set("web-1", entry)

    reopened = node_relay.NodeRelayStore(tmp_path)

    assert reopened.get("web-1") == entry
    assert reopened.names() == {"web-1"}
    assert reopened.remove("web-1") is True
    assert reopened.remove("web-1") is False
    if os.name != "nt":
        assert (tmp_path / ".node_relay.json").stat().st_mode & 0o777 == 0o600


def test_corrupt_node_store_is_a_named_error(tmp_path):
    (tmp_path / ".node_relay.json").write_text("[]", encoding="utf-8")
    store = node_relay.NodeRelayStore(tmp_path)

    assert store.load() == {}
    assert "corrupt" in store.last_error.lower()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("relay.test:9997", ("relay.test", 9997)),
        ("[::1]:9997", ("::1", 9997)),
        ("[2001:db8::5]:443", ("2001:db8::5", 443)),
    ],
)
def test_relay_url_parses_host_and_port(url, expected):
    assert node_relay.split_relay_url(url) == expected


@pytest.mark.parametrize(
    "url",
    ["relay.test", "relay.test:notaport", "[::1]", "::1", "relay.test:0", "relay.test:70000"],
)
def test_relay_url_without_a_valid_port_is_a_named_error(url):
    with pytest.raises(node_relay.RelayError, match="host:port"):
        node_relay.split_relay_url(url)


def test_admin_client_enroll_and_revoke_against_a_real_relay(tmp_path):
    server = start_relay(tmp_path)
    client = node_relay.RelayAdminClient(
        f"127.0.0.1:{server.address[1]}", server.admin_key, server.fingerprint
    )
    try:
        assert client.enroll(RELAY_ID, TOKEN, pool=2)["data"]["success"] is True
        assert client.status()["type"] == "status"
        assert client.ping()["type"] == "pong"
        assert client.revoke(RELAY_ID)["data"]["success"] is True
    finally:
        server.stop()


def test_admin_client_refuses_a_fingerprint_mismatch(tmp_path):
    server = start_relay(tmp_path)
    client = node_relay.RelayAdminClient(
        f"127.0.0.1:{server.address[1]}", server.admin_key, "00" * 32
    )
    with pytest.raises(node_relay.RelayError, match="identity mismatch"):
        client.status()
    server.stop()


def test_admin_client_requires_an_admin_key(tmp_path):
    with pytest.raises(node_relay.RelayError, match="admin key"):
        node_relay.RelayAdminClient("relay.test:9997", "", "ab" * 32)


def test_relay_transport_reports_node_offline(tmp_path):
    server = start_relay(tmp_path, pair_timeout=0.2)
    transport = make_transport(server)
    try:
        with pytest.raises(node_relay.RelayError, match="node offline"):
            transport.connect()
    finally:
        server.stop()


def test_relay_transport_rejects_a_relay_identity_mismatch(tmp_path):
    server = start_relay(tmp_path, pair_timeout=0.2)
    transport = make_transport(server, relay_fingerprint="00" * 32)
    try:
        with pytest.raises(node_relay.RelayError, match="identity mismatch"):
            transport.connect()
    finally:
        server.stop()
