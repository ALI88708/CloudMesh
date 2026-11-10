import json
import secrets
import socket
import ssl
import threading
import time
from pathlib import Path

import pytest

from cloudmesh.node import cloudmesh_relay as relay

RELAY_ID = "ab" * 16
TOKEN = "cd" * 32
ADMIN_KEY = "11" * 32


def now():
    return int(time.time())


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def tls_connect(server):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    raw = socket.create_connection(server.address, timeout=2)
    return context.wrap_socket(raw, server_hostname="relay.test")


def start_relay(tmp_path, pair_timeout=0.3, capture=False):
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
    server = relay.RelayServer(
        config, registry=registry, pair_timeout=pair_timeout, capture=capture
    )
    server.start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def connect_and_register(server, relay_id, token, nonce=None):
    sock = tls_connect(server)
    ts = now()
    nonce = nonce or secrets.token_hex(8)
    relay.send_frame(
        sock,
        {
            "type": "register",
            "relay_id": relay_id,
            "ts": ts,
            "nonce": nonce,
            "mac": relay.register_mac(token, relay_id, ts, nonce),
        },
    )
    reply = relay.recv_frame(sock)
    if not reply or reply.get("type") != "parked":
        sock.close()
        message = (reply or {}).get("message", "no reply")
        raise relay.RelayError(message)
    return sock


def connect_register_expect_error(server, relay_id, token, nonce=None):
    sock = tls_connect(server)
    ts = now()
    nonce = nonce or secrets.token_hex(8)
    relay.send_frame(
        sock,
        {
            "type": "register",
            "relay_id": relay_id,
            "ts": ts,
            "nonce": nonce,
            "mac": relay.register_mac(token, relay_id, ts, nonce),
        },
    )
    return sock


def connect_controller(server, relay_id, client_id, nonce=None):
    sock = tls_connect(server)
    ts = now()
    nonce = nonce or secrets.token_hex(8)
    relay.send_frame(
        sock,
        {
            "type": "connect",
            "relay_id": relay_id,
            "client_id": client_id,
            "ts": ts,
            "nonce": nonce,
            "mac": relay.connect_mac(ADMIN_KEY, relay_id, client_id, ts, nonce),
        },
    )
    return sock


def admin(server, action, relay_id="", **extra):
    sock = tls_connect(server)
    ts = now()
    nonce = secrets.token_hex(8)
    payload = {
        "type": "admin",
        "action": action,
        "relay_id": relay_id,
        "ts": ts,
        "nonce": nonce,
        "mac": relay.admin_mac(ADMIN_KEY, action, relay_id, ts, nonce),
    }
    payload.update(extra)
    try:
        relay.send_frame(sock, payload)
        return relay.recv_frame(sock)
    finally:
        sock.close()


def test_registered_node_is_parked_and_reports_status(tmp_path):
    server = start_relay(tmp_path)
    node = connect_and_register(server, RELAY_ID, TOKEN)
    try:
        assert wait_for(lambda: server.stats()["nodes"][RELAY_ID]["parked"] == 1)
        status = admin(server, "status")
        assert status["type"] == "status"
        assert status["data"]["totals"]["parked"] == 1
    finally:
        node.close()
        server.stop()


def test_controller_is_paired_with_parked_node_and_bytes_flow(tmp_path):
    server = start_relay(tmp_path)
    node = connect_and_register(server, RELAY_ID, TOKEN)
    controller = connect_controller(server, RELAY_ID, "ab" * 16)
    try:
        assert relay.recv_frame(node)["type"] == "paired"
        assert relay.recv_frame(controller)["type"] == "paired"
        controller.sendall(b"secret-from-controller")
        assert node.recv(len(b"secret-from-controller")) == b"secret-from-controller"
        node.sendall(b"secret-from-node")
        assert controller.recv(len(b"secret-from-node")) == b"secret-from-node"
    finally:
        node.close()
        controller.close()
        server.stop()


def test_connect_without_parked_node_returns_node_offline(tmp_path):
    server = start_relay(tmp_path)
    controller = connect_controller(server, RELAY_ID, "ab" * 16)
    try:
        assert relay.recv_frame(controller) == {
            "type": "error",
            "message": "node offline",
        }
    finally:
        controller.close()
        server.stop()


def test_register_with_an_unknown_relay_id_is_rejected(tmp_path):
    server = start_relay(tmp_path)
    with pytest.raises(relay.RelayError):
        connect_and_register(server, "ff" * 16, TOKEN)
    server.stop()


def test_revoke_closes_parked_connections(tmp_path):
    server = start_relay(tmp_path)
    node = connect_and_register(server, RELAY_ID, TOKEN)
    try:
        assert admin(server, "revoke", RELAY_ID)["data"]["success"] is True
        assert node.recv(1) == b""
    finally:
        node.close()
        server.stop()


def test_duplicate_parked_registration_beyond_pool_is_rejected(tmp_path):
    server = start_relay(tmp_path)
    first = connect_and_register(server, RELAY_ID, TOKEN)
    second = connect_and_register(server, RELAY_ID, TOKEN)
    third = connect_register_expect_error(server, RELAY_ID, TOKEN)
    try:
        assert relay.recv_frame(third)["message"] == "too many registrations"
    finally:
        for sock in (first, second, third):
            sock.close()
        server.stop()


def test_replayed_nonce_is_rejected(tmp_path):
    server = start_relay(tmp_path)
    nonce = "ab" * 8
    first = connect_and_register(server, RELAY_ID, TOKEN, nonce=nonce)
    replay = connect_register_expect_error(server, RELAY_ID, TOKEN, nonce=nonce)
    try:
        assert relay.recv_frame(replay)["message"] == "unauthorized"
    finally:
        first.close()
        replay.close()
        server.stop()


def test_missing_certificate_refuses_to_start(tmp_path):
    config = relay.RelayConfig(
        bind="127.0.0.1",
        port=0,
        admin_key=ADMIN_KEY,
        tls_cert=str(tmp_path / "missing.pem"),
        tls_key=str(tmp_path / "missing-key.pem"),
        tokens_file=str(tmp_path / "tokens.json"),
    )
    with pytest.raises(relay.RelayError):
        relay.RelayServer(config).start()


def test_admin_rejects_a_bad_mac(tmp_path):
    server = start_relay(tmp_path)
    sock = tls_connect(server)
    ts = now()
    nonce = secrets.token_hex(8)
    try:
        relay.send_frame(
            sock,
            {
                "type": "admin",
                "action": "status",
                "relay_id": "",
                "ts": ts,
                "nonce": nonce,
                "mac": "00" * 32,
            },
        )
        assert relay.recv_frame(sock)["message"] == "unauthorized"
    finally:
        sock.close()
        server.stop()


def test_config_round_trip_resolves_relative_paths(tmp_path):
    (tmp_path / "certs").mkdir()
    cert = tmp_path / "certs" / "relay-cert.pem"
    key = tmp_path / "certs" / "relay-key.pem"
    relay.generate_self_signed_cert(cert, key, "relay.test")
    config = relay.RelayConfig(
        bind="0.0.0.0",
        port=9997,
        admin_key=ADMIN_KEY,
        tls_cert="certs/relay-cert.pem",
        tls_key="certs/relay-key.pem",
        tokens_file="tokens.json",
    )
    path = tmp_path / "relay.json"
    config.save(path)

    loaded = relay.RelayConfig.load(path)

    assert loaded.port == 9997
    assert Path(loaded.tls_cert) == cert
    assert Path(loaded.tokens_file) == tmp_path / "tokens.json"


def test_corrupt_config_is_a_named_error(tmp_path):
    path = tmp_path / "relay.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(relay.RelayError, match="relay config is corrupt"):
        relay.RelayConfig.load(path)


def test_auth_failure_burst_bans_one_ip():
    limiter = relay._HandshakeLimiter(
        attempts=60, window=60, concurrent=20, failures=3, ban_seconds=300
    )
    for _ in range(3):
        limiter.on_failure("203.0.113.5")
    assert limiter.check("203.0.113.5") is False
    assert limiter.check("203.0.113.6") is True


def test_capture_records_forwarded_bytes(tmp_path):
    server = start_relay(tmp_path, capture=True)
    node = connect_and_register(server, RELAY_ID, TOKEN)
    controller = connect_controller(server, RELAY_ID, "ab" * 16)
    try:
        relay.recv_frame(node)
        relay.recv_frame(controller)
        controller.sendall(b"relay-capture-probe")
        assert node.recv(19) == b"relay-capture-probe"
        assert wait_for(lambda: b"relay-capture-probe" in server.captured_bytes())
    finally:
        node.close()
        controller.close()
        server.stop()


def test_stats_report_registrations_and_auth_failures(tmp_path):
    server = start_relay(tmp_path)
    node = connect_and_register(server, RELAY_ID, TOKEN)
    try:
        sock = tls_connect(server)
        relay.send_frame(sock, {"type": "register", "relay_id": "zz"})
        relay.recv_frame(sock)
        sock.close()
        assert wait_for(
            lambda: server.stats()["totals"]["auth_failures"] >= 1
        )
        assert server.stats()["totals"]["registrations"] == 1
    finally:
        node.close()
        server.stop()

