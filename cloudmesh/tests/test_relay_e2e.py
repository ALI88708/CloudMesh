"""End-to-end acceptance for relay mode.

The real relay, the real node agent, and the real controller transport are used
together. Nothing is stubbed: a passing test here means a node behind NAT can
be pinged, executed against, uploaded to, and used for async jobs.
"""

import socket
import threading
import time

import pytest

from cloudmesh.core.node_client import NodeClient
from cloudmesh.node import cloudmesh_node as node_module
from cloudmesh.node import cloudmesh_relay as relay
from cloudmesh.node.cloudmesh_node import NodeAgent

pytestmark = pytest.mark.timeout(60)

RELAY_ID = "ab" * 16
TOKEN = "cd" * 32
ADMIN_KEY = "11" * 32
AUTH_KEY = "9f3c1d7a5b2e8046"
CLIENT_ID = "ef" * 16
WRONG_FINGERPRINT = "00" * 32


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def start_relay(tmp_path, port=0, capture=False):
    cert = tmp_path / "relay-cert.pem"
    key = tmp_path / "relay-key.pem"
    if not cert.exists():
        relay.generate_self_signed_cert(cert, key, "relay.test")
    registry = relay.TokenRegistry(tmp_path / "tokens.json")
    registry.add(RELAY_ID, TOKEN, pool=4)
    config = relay.RelayConfig(
        bind="127.0.0.1",
        port=port,
        admin_key=ADMIN_KEY,
        tls_cert=str(cert),
        tls_key=str(key),
        tokens_file=str(tmp_path / "tokens.json"),
    )
    server = relay.RelayServer(
        config, registry=registry, pair_timeout=0.3, capture=capture
    )
    server.start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def node_credentials(tmp_path):
    cert = tmp_path / "node-cert.pem"
    key = tmp_path / "node-key.pem"
    fingerprint = relay.generate_self_signed_cert(cert, key, RELAY_ID)
    return cert, key, fingerprint


def node_config(server, cert, key, pool=2):
    return {
        "relay_id": RELAY_ID,
        "url": f"127.0.0.1:{server.address[1]}",
        "node_token": TOKEN,
        "relay_fingerprint": server.fingerprint,
        "tls_cert": str(cert),
        "tls_key": str(key),
        "pool": pool,
    }


def controller(server, node_fingerprint):
    entry = {
        "relay_id": RELAY_ID,
        "url": f"127.0.0.1:{server.address[1]}",
        "relay_fingerprint": server.fingerprint,
        "node_fingerprint": node_fingerprint,
    }
    profile = {
        "admin_key": server.admin_key,
        "relay_fingerprint": server.fingerprint,
        "ca_file": None,
    }
    return NodeClient(
        "127.0.0.1",
        server.address[1],
        AUTH_KEY,
        transport="relay",
        relay_entry=entry,
        relay_profile=profile,
        client_id=CLIENT_ID,
    )


def start_full_stack(
    tmp_path, monkeypatch, *, capture=False, wrong_fingerprint=False, port=0
):
    """Start relay, agent, and controller; return them ready to talk."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(node_module, "BASE_DIR", tmp_path)
    monkeypatch.setattr(node_module, "JOBS_DIR", tmp_path / "jobs")
    server = start_relay(tmp_path, port=port, capture=capture)
    cert, key, fingerprint = node_credentials(tmp_path)
    agent = NodeAgent(
        port=0,
        auth_key=AUTH_KEY,
        bind_host="127.0.0.1",
        relay_config=node_config(server, cert, key, pool=2),
    )
    agent.start_relay_only_for_test()
    client = controller(
        server, WRONG_FINGERPRINT if wrong_fingerprint else fingerprint
    )
    assert wait_for(lambda: agent.relay_status()["connected_slots"] == 2)
    return server, agent, client


def stop_full_stack(server, agent):
    agent.stop_relay_for_test()
    server.stop()


def test_execute_info_upload_and_job_through_the_relay(tmp_path, monkeypatch):
    server, agent, client = start_full_stack(tmp_path, monkeypatch)
    try:
        assert client.ping() is True
        assert client.execute("echo relay-ok")["stdout"].strip() == "relay-ok"
        assert client.get_info()["hostname"]
        assert client.upload_file("data/note.txt", "hello")["success"] is True
        assert client.download_file("data/note.txt")["content"] == "hello"
        job = client.start_job("echo done")
        assert job["job_id"]
        assert wait_for(
            lambda: (client.check_job(job["job_id"]) or {}).get("status")
            == "completed"
        )
    finally:
        stop_full_stack(server, agent)


def test_relay_capture_contains_no_plaintext(tmp_path, monkeypatch):
    server, agent, client = start_full_stack(tmp_path, monkeypatch, capture=True)
    try:
        client.execute("echo TOP-SECRET-OUTPUT")
        captured = server.captured_bytes()
        assert captured
        assert b"TOP-SECRET-OUTPUT" not in captured
        assert b"echo TOP-SECRET-OUTPUT" not in captured
        assert AUTH_KEY.encode() not in captured
    finally:
        stop_full_stack(server, agent)


@pytest.mark.timeout(60)
def test_relay_restart_keeps_the_node_usable(tmp_path, monkeypatch):
    server, agent, client = start_full_stack(tmp_path, monkeypatch)
    port = server.address[1]
    server.stop()
    server = start_relay(tmp_path, port=port)
    try:
        assert wait_for(client.ping, timeout=8)
    finally:
        stop_full_stack(server, agent)


def test_wrong_node_certificate_never_receives_the_auth_key(tmp_path, monkeypatch):
    server, agent, client = start_full_stack(
        tmp_path, monkeypatch, wrong_fingerprint=True
    )
    try:
        result = client.execute("id")
        assert result["message"].lower().startswith("relay node identity mismatch")
        assert agent.received_application_bytes() == 0
    finally:
        stop_full_stack(server, agent)


def test_revoked_token_cannot_re_register(tmp_path, monkeypatch):
    server, agent, _client = start_full_stack(tmp_path, monkeypatch)
    try:
        assert server.revoke(RELAY_ID) is True
        assert wait_for(
            lambda: agent.relay_status()["last_error"] is not None, timeout=5
        )
    finally:
        stop_full_stack(server, agent)
