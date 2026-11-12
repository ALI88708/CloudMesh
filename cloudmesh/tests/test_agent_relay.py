import json
import socket
import threading
import time
from pathlib import Path

import pytest

from cloudmesh.core.node_client import NodeClient
from cloudmesh.node import cloudmesh_relay as relay
from cloudmesh.node.cloudmesh_node import (
    RELAY_CONFIG_FILE,
    NodeAgent,
    load_relay_config,
)

RELAY_ID = "ab" * 16
TOKEN = "cd" * 32
ADMIN_KEY = "11" * 32
AUTH_KEY = "auth"
CLIENT_ID = "ef" * 16


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


def start_relay(tmp_path, port=0):
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
    server = relay.RelayServer(config, registry=registry, pair_timeout=0.3)
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


def make_agent(server, cert, key, pool=2, **kwargs):
    return NodeAgent(
        port=0,
        auth_key=AUTH_KEY,
        bind_host="127.0.0.1",
        relay_config=node_config(server, cert, key, pool=pool),
        **kwargs,
    )


def test_stop_waits_for_the_serve_loop_to_leave_the_listener():
    server = relay.RelayServer.__new__(relay.RelayServer)
    server._stop = threading.Event()
    server._listener = None
    server._parking = relay.ParkingRegistry()
    server._lock = threading.Lock()
    server._active_sockets = set()
    server._serve_thread = None

    entered = threading.Event()
    release = threading.Event()

    def serve_loop():
        entered.set()
        server._stop.wait()
        release.wait(2.0)

    loop_thread = threading.Thread(target=serve_loop)
    server._serve_thread = loop_thread
    loop_thread.start()
    assert entered.wait(1.0)

    alive_at_return = []
    stopped = threading.Event()

    def run_stop():
        server.stop()
        alive_at_return.append(loop_thread.is_alive())
        stopped.set()

    threading.Thread(target=run_stop).start()
    assert server._stop.wait(1.0)
    time.sleep(0.1)
    release.set()
    assert stopped.wait(2.0)
    assert alive_at_return == [False]


def test_parking_registry_rejects_connections_after_shutdown():
    class FakeParked:
        relay_id = RELAY_ID

        def __init__(self):
            self.closed = threading.Event()

    registry = relay.ParkingRegistry()
    registry.close_everything()

    assert registry.park(FakeParked(), 4) is False


def test_agent_parks_the_configured_pool(tmp_path):
    server = start_relay(tmp_path)
    cert, key, _ = node_credentials(tmp_path)
    agent = make_agent(server, cert, key, pool=2)
    agent.start_relay_only_for_test()
    try:
        assert wait_for(lambda: agent.relay_status()["connected_slots"] == 2)
        assert wait_for(
            lambda: server.stats()["nodes"].get(RELAY_ID, {}).get("parked") == 2
        )
    finally:
        agent.stop_relay_for_test()
        server.stop()


def test_agent_replenishes_a_slot_after_pairing(tmp_path):
    server = start_relay(tmp_path)
    cert, key, fingerprint = node_credentials(tmp_path)
    agent = make_agent(server, cert, key, pool=2)
    client = controller(server, fingerprint)
    agent.start_relay_only_for_test()
    try:
        assert wait_for(lambda: agent.relay_status()["connected_slots"] == 2)
        assert client.ping() is True
        assert wait_for(lambda: agent.relay_status()["connected_slots"] == 2)
    finally:
        agent.stop_relay_for_test()
        server.stop()


def test_relay_only_agent_does_not_open_the_direct_port(tmp_path):
    server = start_relay(tmp_path)
    cert, key, _ = node_credentials(tmp_path)
    port = free_port()
    agent = NodeAgent(
        port=port,
        auth_key=AUTH_KEY,
        bind_host="127.0.0.1",
        relay_config=node_config(server, cert, key, pool=1),
        relay_only=True,
    )
    threading.Thread(target=agent.serve, daemon=True).start()
    try:
        assert wait_for(lambda: agent.relay_status()["connected_slots"] == 1)
        # Windows loopback can time out instead of refusing on a closed port;
        # either failure mode proves nothing is listening.
        with pytest.raises((ConnectionRefusedError, TimeoutError)):
            socket.create_connection(("127.0.0.1", port), timeout=0.5)
    finally:
        agent.stop()
        server.stop()


def test_incomplete_relay_config_is_a_named_error(tmp_path):
    path = tmp_path / ".node_relay.json"
    path.write_text('{"relay_id": "ab"}', encoding="utf-8")

    with pytest.raises(ValueError, match="relay config is incomplete"):
        load_relay_config(path)


def test_relay_config_file_lives_beside_the_agent():
    assert RELAY_CONFIG_FILE.name == ".node_relay.json"


def test_load_relay_config_resolves_paths_relative_to_the_file(tmp_path):
    cert, key, _ = node_credentials(tmp_path)
    path = tmp_path / ".node_relay.json"
    path.write_text(
        json.dumps(
            {
                "relay_id": RELAY_ID,
                "url": "relay.test:9997",
                "node_token": TOKEN,
                "relay_fingerprint": "12" * 32,
                "tls_cert": cert.name,
                "tls_key": key.name,
                "pool": 2,
            }
        ),
        encoding="utf-8",
    )

    config = load_relay_config(path)

    assert Path(config["tls_cert"]) == cert.resolve()
    assert Path(config["tls_key"]) == key.resolve()
    assert config["pool"] == 2


@pytest.mark.parametrize("pool", [0, 33, "two"])
def test_relay_config_rejects_a_bad_pool(tmp_path, pool):
    cert, key, _ = node_credentials(tmp_path)
    path = tmp_path / ".node_relay.json"
    path.write_text(
        json.dumps(
            {
                "relay_id": RELAY_ID,
                "url": "relay.test:9997",
                "node_token": TOKEN,
                "relay_fingerprint": "12" * 32,
                "tls_cert": cert.name,
                "tls_key": key.name,
                "pool": pool,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="pool"):
        load_relay_config(path)


def test_agent_info_includes_relay_state(tmp_path):
    server = start_relay(tmp_path)
    cert, key, _ = node_credentials(tmp_path)
    agent = make_agent(server, cert, key, pool=1)
    agent.start_relay_only_for_test()
    try:
        assert wait_for(lambda: agent.relay_status()["connected_slots"] == 1)
        relay_info = agent.info["relay"]
        assert relay_info["enabled"] is True
        assert relay_info["url"].startswith("127.0.0.1:")
        assert relay_info["pool_size"] == 1
        assert relay_info["last_error"] is None
        assert relay_info["last_connected_at"] is not None
    finally:
        agent.stop_relay_for_test()
        server.stop()


def test_agent_without_relay_reports_it_disabled(tmp_path):
    agent = NodeAgent(port=0, auth_key=AUTH_KEY, bind_host="127.0.0.1")

    assert agent.info["relay"] == {"enabled": False}


@pytest.mark.timeout(60)
def test_agent_reconnects_after_relay_restart(tmp_path):
    first = start_relay(tmp_path)
    port = first.address[1]
    cert, key, _ = node_credentials(tmp_path)
    agent = make_agent(first, cert, key, pool=2)
    agent.start_relay_only_for_test()
    assert wait_for(lambda: agent.relay_status()["connected_slots"] == 2)
    first.stop()

    second = start_relay(tmp_path, port=port)
    try:
        assert wait_for(lambda: agent.relay_status()["connected_slots"] == 2, timeout=8)
    finally:
        agent.stop_relay_for_test()
        second.stop()
