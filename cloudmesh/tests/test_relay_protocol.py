import os
import socket

import pytest

from cloudmesh.node import cloudmesh_relay as relay


def test_frame_round_trip():
    left, right = socket.socketpair()
    try:
        relay.send_frame(left, {"type": "ping", "n": 1})
        assert relay.recv_frame(right) == {"type": "ping", "n": 1}
    finally:
        left.close()
        right.close()


def test_frame_rejects_oversized_and_malformed():
    left, right = socket.socketpair()
    try:
        left.sendall((relay.MAX_FRAME_BYTES + 1).to_bytes(4, "big") + b"{}")
        assert relay.recv_frame(right) is None
    finally:
        left.close()
        right.close()

    left, right = socket.socketpair()
    try:
        left.sendall((7).to_bytes(4, "big") + b"notjson")
        assert relay.recv_frame(right) is None
    finally:
        left.close()
        right.close()


def test_register_mac_matches_documented_formula():
    # Independent vector: HMAC-SHA256(key, "register|<relay_id>|<ts>|<nonce>").
    assert relay.register_mac("00" * 32, "11" * 16, 1700000000, "22" * 8) == (
        "aafc2e5fa28530f986fe017250e07fe721095ccc4db5fe006063021a161367a5"
    )


def test_connect_and_admin_mac_use_their_fields():
    assert relay.connect_mac("aa" * 32, "bb" * 16, "cc" * 16, 7, "dd" * 8) != (
        relay.admin_mac("aa" * 32, "status", "bb" * 16, 7, "dd" * 8)
    )
    assert relay.verify_mac("abc", "abc") is True
    assert relay.verify_mac("abc", "abd") is False


def test_nonce_replay_and_clock_skew_are_rejected():
    cache = relay.NonceCache(ttl=60, capacity=10)
    ok, reason = cache.accept("node", "ab" * 8, 1000, now=1000)
    assert (ok, reason) == (True, "")
    assert cache.accept("node", "ab" * 8, 1000, now=1001)[0] is False
    assert cache.accept("node", "cd" * 8, 1000, now=1100)[0] is False


def test_nonce_cache_rejects_malformed_nonce():
    cache = relay.NonceCache(ttl=60, capacity=10)
    assert cache.accept("node", "not-hex", 1000, now=1000)[0] is False


def test_token_registry_round_trip(tmp_path):
    path = tmp_path / "tokens.json"
    registry = relay.TokenRegistry(path)
    relay_id = "ab" * 16
    registry.add(relay_id, "cd" * 32, pool=4)

    reopened = relay.TokenRegistry(path)

    assert reopened.verify(relay_id, "cd" * 32) is True
    assert reopened.verify(relay_id, "ee" * 32) is False
    assert reopened.pool_for(relay_id) == 4
    assert reopened.count() == 1
    assert reopened.remove(relay_id) is True
    assert reopened.count() == 0
    if os.name != "nt":
        assert (path.stat().st_mode & 0o777) == 0o600


def test_token_registry_rejects_a_corrupt_file(tmp_path):
    path = tmp_path / "tokens.json"
    path.write_text("{not json", encoding="utf-8")
    registry = relay.TokenRegistry(path)

    assert registry.load() == {}
    assert "corrupt" in (registry.last_error or "").lower()
    with pytest.raises(relay.RelayError):
        registry.add("ab" * 16, "cd" * 32)


def test_token_registry_validates_identifiers(tmp_path):
    registry = relay.TokenRegistry(tmp_path / "tokens.json")
    with pytest.raises(ValueError):
        registry.add("not-hex", "cd" * 32)
    with pytest.raises(ValueError):
        registry.add("ab" * 16, "short")
    with pytest.raises(ValueError):
        registry.add("ab" * 16, "cd" * 32, pool=0)
    with pytest.raises(ValueError):
        registry.add("ab" * 16, "cd" * 32, pool=33)


def test_certificate_fingerprint_is_sha256_of_der(tmp_path):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    fingerprint = relay.generate_self_signed_cert(cert, key, "node-1")
    assert len(fingerprint) == 64
    assert relay.cert_fingerprint(cert) == fingerprint
    if os.name != "nt":
        assert (key.stat().st_mode & 0o777) == 0o600
        assert (cert.stat().st_mode & 0o777) == 0o644
