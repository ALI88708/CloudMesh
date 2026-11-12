import json
import socket

import pytest

from cloudmesh.node.cloudmesh_node import NodeAgent

CLIENT_ONE = "ab" * 16
CLIENT_TWO = "cd" * 16


@pytest.fixture
def agent():
    return NodeAgent(port=0, auth_key="auth", bind_host="127.0.0.1")


def relay_key(client_id):
    return "relay:" + client_id


def feed_bad_auth(agent, client_id, auth="wrong"):
    local, peer = socket.socketpair()
    try:
        payload = json.dumps({"action": "ping", "auth": auth}).encode()
        peer.sendall(len(payload).to_bytes(4, "big") + payload)
        agent._handle(local, ("relay", 0), client_id=client_id)
    finally:
        peer.close()
        local.close()


def test_relay_requests_are_limited_per_client_id(agent):
    key = agent._rate_key(CLIENT_ONE, "relay")
    assert key == relay_key(CLIENT_ONE)
    for _ in range(120):
        allowed, _reason = agent._relay_ddos.check_connection(key)
        assert allowed is True
        agent._relay_ddos.release_connection(key)

    allowed, reason = agent._relay_ddos.check_connection(key)

    assert allowed is False
    assert "rate" in reason.lower()


def test_one_client_ban_does_not_affect_another(agent):
    for _ in range(agent._relay_ddos.ban_threshold):
        agent._relay_ddos.on_auth_failure(relay_key(CLIENT_ONE))

    assert agent._relay_ddos.check_connection(relay_key(CLIENT_ONE))[0] is False
    assert agent._relay_ddos.check_connection(relay_key(CLIENT_TWO))[0] is True


def test_direct_mode_still_limits_per_ip(agent):
    for _ in range(30):
        allowed, _reason = agent._ddos.check_connection("203.0.113.5")
        assert allowed is True
        agent._ddos.release_connection("203.0.113.5")

    assert agent._ddos.check_connection("203.0.113.5")[0] is False


def test_malformed_client_id_is_rejected_without_crashing(agent):
    with pytest.raises(ValueError):
        agent._rate_key("not-hex", "relay")


def test_auth_failure_bans_only_that_client(agent):
    for _ in range(agent._relay_ddos.ban_threshold):
        feed_bad_auth(agent, CLIENT_ONE)

    assert agent._relay_ddos.check_connection(relay_key(CLIENT_ONE))[0] is False
    allowed, reason = agent._relay_ddos.check_connection(relay_key(CLIENT_TWO))
    assert allowed is True, reason


def test_a_malformed_client_id_closes_the_connection_without_counting(agent):
    feed_bad_auth(agent, "not-hex")

    assert agent._relay_ddos.check_connection(relay_key(CLIENT_TWO))[0] is True
