# Node Relay (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a CloudMesh node reachable through an outbound-only relay, with TLS on both legs, per-node tokens, and no change to direct-mode behavior.

**Architecture:** A standalone stdlib relay server pairs a parked node connection with a controller connection and forwards raw bytes. The node keeps a pool of parked connections; the controller pairs per request, then runs the existing JSON protocol inside an inner TLS session whose node certificate fingerprint is pinned. Provisioning travels over SSH, or happens locally on the node with a one-line import on the controller.

**Tech Stack:** Python 3.11+ (dev runs 3.14), stdlib `socket`/`ssl`/`hmac`/`threading`, `cryptography` for certificate generation, `pytest`, `pytest-timeout`.

**Spec:** `docs/superpowers/specs/2026-11-05-node-relay-design.md`

## Global Constraints

- Python floor is 3.11 on the controller; the agent keeps its current floor.
- `cloudmesh/node/cloudmesh_node.py` and `cloudmesh/node/cloudmesh_relay.py` must not import `cloudmesh.core`. The relay module uses only the standard library at import time; `cryptography` is imported lazily inside certificate generation.
- No plaintext fallback on either leg. Missing certificates or fingerprints are named errors, never a downgrade.
- `NodeKeyring` schema stays unchanged. Relay settings live in `.relays.json` and `.node_relay.json` sidecars.
- Every sidecar is written atomically and is `0600` on POSIX. Windows skips the mode assertion.
- The relay's parked cap counts parked connections only; paired connections do not count.
- `pytest.ini` sets a 10-second per-test timeout. Tests that wait for pairing use a `pair_timeout` of 0.2–0.5 seconds, never the 5-second production default.
- Tests must pass on Windows. POSIX-only assertions use `os.name != "nt"` guards.
- TDD: write the failing test, run it, implement the smallest change, run it again, commit.
- Full verification command at the end of each task: `python -m pytest cloudmesh/tests -q`.
- Version target is 4.3.0; do not bump version surfaces until Task 11.

## Review Focus

These are the failure modes the spec implies but no single task's happy-path test covers. Each line is pinned to a test in the owning task.

1. **A relay URL without a port, or an IPv6 literal without brackets.** A user typing `cm relay add --url relay.example.com` must get `relay URL must be host:port`, not a traceback or a connection to port 0. Pinned in Task 4.
2. **A node with a corrupt or partial relay sidecar.** `NodeClient` must return `relay config is corrupt: ...` or `relay config is incomplete: ...`; it must never silently fall back to direct mode. Pinned in Task 5.
3. **A certificate file that is missing or unreadable.** `cm relay serve` and the agent must refuse to start, and the controller must refuse to pair; no plaintext listener appears. Pinned in Tasks 2, 3, 5, and 6.
4. **A stale timestamp or replayed nonce.** The relay closes the connection with `unauthorized` and does not crash or leak whether the relay ID exists. Pinned in Task 2.
5. **More controllers than parked slots.** The extra connect waits, then returns `node offline`; every socket is closed, and the test finishes well inside the 10-second timeout. Pinned in Task 2.

---

## Task 1: Relay protocol primitives and token registry

**Files:**
- Create: `cloudmesh/node/cloudmesh_relay.py`
- Test: `cloudmesh/tests/test_relay_protocol.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class RelayError(Exception)`
  - `MAX_FRAME_BYTES = 64 * 1024`
  - `def encode_frame(payload: dict) -> bytes`
  - `def recv_frame(sock, max_bytes: int = MAX_FRAME_BYTES) -> dict | None`
  - `def send_frame(sock, payload: dict) -> None`
  - `def register_mac(token: str, relay_id: str, ts: int, nonce: str) -> str`
  - `def connect_mac(admin_key: str, relay_id: str, client_id: str, ts: int, nonce: str) -> str`
  - `def admin_mac(admin_key: str, action: str, relay_id: str, ts: int, nonce: str) -> str`
  - `def verify_mac(expected: str, supplied: str) -> bool`
  - `class NonceCache` with `accept(scope, nonce, ts, now=None) -> tuple[bool, str]`
  - `class TokenRegistry` with `load`, `add(relay_id, token, pool=4)`, `remove`, `verify`, `pool_for`, `count`, and `last_error`
  - `def cert_fingerprint(cert_path: Path) -> str`
  - `def der_fingerprint(der: bytes) -> str`
  - `def generate_self_signed_cert(cert_path: Path, key_path: Path, common_name: str, days: int = 3650) -> str`

- [ ] **Step 1: Write the failing protocol tests**

```python
import json
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


def test_nonce_replay_and_clock_skew_are_rejected(tmp_path):
    cache = relay.NonceCache(ttl=60, capacity=10)
    ok, reason = cache.accept("node", "ab" * 8, 1000, now=1000)
    assert (ok, reason) == (True, "")
    assert cache.accept("node", "ab" * 8, 1000, now=1001)[0] is False
    assert cache.accept("node", "cd" * 8, 1000, now=1100)[0] is False


def test_token_registry_round_trip(tmp_path):
    path = tmp_path / "tokens.json"
    registry = relay.TokenRegistry(path)
    relay_id = "ab" * 16
    registry.add(relay_id, "cd" * 32, pool=4)

    reopened = relay.TokenRegistry(path)

    assert reopened.verify(relay_id, "cd" * 32) is True
    assert reopened.verify(relay_id, "ee" * 32) is False
    assert reopened.pool_for(relay_id) == 4
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


def test_certificate_fingerprint_is_sha256_of_der(tmp_path):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    fingerprint = relay.generate_self_signed_cert(cert, key, "node-1")
    assert len(fingerprint) == 64
    assert relay.cert_fingerprint(cert) == fingerprint
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cloudmesh/tests/test_relay_protocol.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'cloudmesh.node.cloudmesh_relay'`.

- [ ] **Step 3: Implement the protocol primitives**

In `cloudmesh/node/cloudmesh_relay.py`, implement:

- `encode_frame`: `len(json.dumps(payload).encode())` as 4-byte big-endian, then the JSON bytes.
- `recv_frame`: read exactly 4 header bytes, reject zero or `> max_bytes`, read the body, return `None` on EOF, timeout, invalid JSON, or a non-dict body.
- `send_frame`: `sock.sendall(encode_frame(payload))`.
- MAC functions: `hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()` with the exact message strings from the spec (`register|...`, `connect|...`, `admin|...`).
- `verify_mac`: `hmac.compare_digest`.
- `NonceCache.accept`: reject a non-hex or wrong-length nonce, reject `abs(now - ts) > 30` with reason `"stale timestamp"`, reject a seen `(scope, nonce)` with `"replayed nonce"`, evict expired entries, cap the dict at `capacity`.
- `TokenRegistry`: validate `relay_id` as 32 hex chars, `token` as 64 hex chars, `pool` as an integer 1–32. `load()` sets `last_error` and returns `{}` for a corrupt file; `add()` raises `RelayError` when `last_error` is set. Store `{relay_id: {"token", "pool", "created_at"}}`. Write with `tempfile.mkstemp` in the parent directory, `os.replace`, and `chmod(0o600)` on POSIX.
- `der_fingerprint`: `hashlib.sha256(der).hexdigest()`.
- `cert_fingerprint`: load PEM, call `der_fingerprint(cert.public_bytes(serialization.Encoding.DER))`.
- `generate_self_signed_cert`: lazy `from cryptography import x509`, ECDSA P-256, `CN=common_name`, `not_valid_after` = now + `days`, write key `0600` and cert `0644`, return the fingerprint.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest cloudmesh/tests/test_relay_protocol.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/node/cloudmesh_relay.py cloudmesh/tests/test_relay_protocol.py
git commit -m "feat: add relay protocol primitives and token registry"
```

---

## Task 2: Relay server pairing, keepalive, and admin API

**Files:**
- Modify: `cloudmesh/node/cloudmesh_relay.py`
- Test: `cloudmesh/tests/test_relay_server.py`

**Interfaces:**
- Consumes: Task 1 primitives.
- Produces:
  - `DEFAULT_RELAY_PORT = 9997`
  - `PAIR_TIMEOUT_SECONDS = 5.0`
  - `class RelayConfig` with `bind`, `port`, `admin_key`, `tls_cert`, `tls_key`, `tokens_file`, `load(path)`, `save(path)`
  - `class RelayServer` with `start() -> tuple[str, int]`, `serve_forever()`, `stop()`, `address`, `stats()`, `revoke(relay_id)`, and `captured_bytes()`
  - `RelayServer(config, registry=None, pair_timeout=PAIR_TIMEOUT_SECONDS, capture=False)`; `capture=True` records every byte the pump forwards so tests can prove the inner leg is ciphertext.
  - `revoke(relay_id)` removes the token from the registry and closes that node's parked connections; it also sets the flag that rejects further registrations for that ID. It returns whether the ID existed.
  - `class ParkingRegistry` with `park`, `take(relay_id, timeout)`, `close_all(relay_id)`, `counts()`

- [ ] **Step 1: Write the failing server tests**

Use `relay.generate_self_signed_cert`. `open_outer_tls` arrives in Task 3, so
this task's tests use a local helper built on `ssl.SSLContext` with
`check_hostname=False` and `verify_mode=CERT_NONE`. The test file defines
`connect_and_register`, `connect_controller`, `connect_register_expect_error`,
`admin`, and `wait_for`; `wait_for` polls every 10 ms with a 2-second cap.
Keep every wait under 1 second by passing `pair_timeout=0.3`.

```python
def start_relay(tmp_path, pair_timeout=0.3):
    cert, key = tmp_path / "relay-cert.pem", tmp_path / "relay-key.pem"
    relay.generate_self_signed_cert(cert, key, "relay.test")
    registry = relay.TokenRegistry(tmp_path / "tokens.json")
    registry.add(RELAY_ID, TOKEN, pool=2)
    config = relay.RelayConfig(
        bind="127.0.0.1", port=0, admin_key=ADMIN_KEY,
        tls_cert=str(cert), tls_key=str(key),
        tokens_file=str(tmp_path / "tokens.json"),
    )
    server = relay.RelayServer(config, registry=registry, pair_timeout=pair_timeout)
    server.start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


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
        assert recv_frame(node)["type"] == "paired"
        assert recv_frame(controller)["type"] == "paired"
        controller.sendall(b"secret-from-controller")
        assert node.recv(21) == b"secret-from-controller"
        node.sendall(b"secret-from-node")
        assert controller.recv(17) == b"secret-from-node"
    finally:
        node.close()
        controller.close()
        server.stop()


def test_connect_without_parked_node_returns_node_offline(tmp_path):
    server = start_relay(tmp_path)
    controller = connect_controller(server, RELAY_ID, "ab" * 16)
    try:
        assert recv_frame(controller) == {"type": "error", "message": "node offline"}
    finally:
        controller.close()
        server.stop()


def test_enroll_then_register_rejects_unknown_relay_id(tmp_path):
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
    server = start_relay(tmp_path)  # pool=2
    first = connect_and_register(server, RELAY_ID, TOKEN)
    second = connect_and_register(server, RELAY_ID, TOKEN)
    third = connect_register_expect_error(server, RELAY_ID, TOKEN)
    try:
        assert recv_frame(third)["message"] == "too many registrations"
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
        assert recv_frame(replay)["message"] == "unauthorized"
    finally:
        first.close()
        replay.close()
        server.stop()
```

Also add `test_missing_certificate_refuses_to_start`: a `RelayConfig` pointing at a missing cert raises `RelayError` from `RelayServer(...).start()` and binds no port.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cloudmesh/tests/test_relay_server.py -q`
Expected: FAIL with `AttributeError: module ... has no attribute 'RelayServer'`.

- [ ] **Step 3: Implement the server**

Implement:

- `RelayConfig.load/save`: JSON with `bind`, `port`, `admin_key`, `tls_cert`, `tls_key`, `tokens_file`; resolve relative cert/token paths against the config file's directory. Missing keys or malformed JSON raise `RelayError("relay config is corrupt: ...")`.
- `RelayServer.__init__`: create the TLS server context with `ssl.PROTOCOL_TLS_SERVER` and `minimum_version = ssl.TLSVersion.TLSv1_2`; load the cert chain; raise `RelayError` if the cert or key is missing. If `registry.last_error` is set, raise `RelayError` (fail closed on a corrupt token file).
- `start()`: bind/listen on `(config.bind, config.port)`, set a 1-second accept timeout, and return the actual address (useful with `port=0`).
- `serve_forever()`: accept in a loop until `stop()`; wrap each socket in the server context and dispatch in a daemon thread.
- `_handle_connection`: read one frame. Dispatch:
  - `register`: validate `relay_id` format, `abs(ts-now) <= 30`, nonce via `NonceCache.accept("register:"+relay_id, ...)`, MAC via `verify_mac(register_mac(token, ...), mac)`, and `registry.verify`. On failure send `{"type":"error","message":"unauthorized"}` and close. On success, create a `ParkedConnection`, enforce `parked < registry.pool_for(relay_id)`, send `{"type":"parked"}`, and enter `parked.wait()`.
  - `connect`: validate admin MAC (including `client_id` as 32 hex chars), call `parking.take(relay_id, pair_timeout)`. If none, send `{"type":"error","message":"node offline"}`. If found, send `{"type":"paired"}` to the controller, then `_pump_pair`.
  - `admin`: validate admin MAC; dispatch `enroll` (`relay_id`, `token`, `pool`), `revoke`, `status`, `ping`.
- `ParkedConnection`: wraps the node socket, `paired` event, `client_id`, and `lock`. `claim(client_id)` acquires the lock, sets `client_id`, sends `{"type":"paired","client_id":...}` to the node, sets `paired`, and releases. The keepalive loop acquires the same lock before sending ping and reading pong, so pairing never races a pong read.
- `_pump_pair`: send `paired` to the controller, wait for the node's claim, then run two daemon threads (`node→controller`, `controller→node`) with 64 KiB chunks; on EOF/error, `shutdown` and close both sockets. Join both threads with a 2-second cap so a stuck side cannot hang the server.
- `stats()`: `{"version": "4.3.0", "uptime_seconds", "nodes": {relay_id: {"parked", "paired"}}, "totals": {"parked", "paired", "registrations", "pairs", "auth_failures"}}`. Use a lock for counters.
- `_HandshakeLimiter`: per-IP 60 attempts/60 s, 20 concurrent, 10 auth failures → 300 s ban. Apply before reading a frame. Tests may skip this class; it is exercised by Task 2's `test_auth_failure_burst_bans_one_ip`.
- Never log frame bodies. Log only `event`, `relay_id`, and IP.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest cloudmesh/tests/test_relay_server.py -q`
Expected: PASS. Every test finishes under 10 seconds.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/node/cloudmesh_relay.py cloudmesh/tests/test_relay_server.py
git commit -m "feat: add relay server pairing and admin API"
```

---

## Task 3: Standalone relay CLI and TLS client helper

**Files:**
- Modify: `cloudmesh/node/cloudmesh_relay.py`
- Modify: `cloudmesh/node/cloudmesh_node.py`
- Test: `cloudmesh/tests/test_relay_cli.py`

**Interfaces:**
- Consumes: Task 2 `RelayServer`, `RelayConfig`.
- Produces:
  - `def open_outer_tls(host: str, port: int, relay_fingerprint: str | None, ca_file: str | None = None, timeout: float = 10.0) -> ssl.SSLSocket`
  - `class InnerTLSSocket` and `def wrap_inner_tls(sock, context: ssl.SSLContext, server_side: bool, server_hostname: str | None = None, timeout: float = 10.0) -> InnerTLSSocket`
  - `def admin_request(host: str, port: int, admin_key: str, relay_fingerprint: str, payload: dict, ca_file: str | None = None, timeout: float = 10.0) -> dict`
  - `def init_relay(config_path: Path, url: str | None = None, bind: str = "0.0.0.0", port: int = DEFAULT_RELAY_PORT, tls_cert: str | None = None, tls_key: str | None = None, days: int = 3650) -> dict`
  - `def serve_relay(config_path: Path, bind: str | None = None, port: int | None = None) -> None`
  - `def main(argv: list[str] | None = None) -> int`
  - `cloudmesh_node.py relay init|serve|status` delegates to `cloudmesh_relay.main`.

- [ ] **Step 1: Write the failing CLI tests**

```python
def test_init_writes_a_private_config_and_certificate(tmp_path):
    config_path = tmp_path / "relay.json"
    result = relay.init_relay(config_path, url="relay.example.com:9997")
    data = json.loads(config_path.read_text())

    assert data["port"] == 9997
    assert data["admin_key"] == result["admin_key"]
    assert Path(result["tls_cert"]).is_file()
    assert Path(result["tls_key"]).is_file()
    assert len(result["relay_fingerprint"]) == 64


def test_serve_refuses_missing_certificate(tmp_path):
    config_path = tmp_path / "relay.json"
    relay.init_relay(config_path)
    config = json.loads(config_path.read_text())
    Path(config["tls_cert"]).unlink()

    with pytest.raises(relay.RelayError):
        relay.serve_relay(config_path)


def test_status_reads_a_running_relay(tmp_path):
    server, config_path, fingerprint = start_relay_with_config(tmp_path)
    try:
        result = relay.admin_request(
            "127.0.0.1", server.address[1], server.admin_key, fingerprint,
            {"type": "admin", "action": "status", "relay_id": "", "ts": now(),
             "nonce": "ab" * 8, "mac": relay.admin_mac(server.admin_key, "status", "", now(), "ab" * 8)},
        )
        assert result["type"] == "status"
    finally:
        server.stop()


def test_main_rejects_an_unknown_subcommand(capsys):
    with pytest.raises(SystemExit):
        relay.main(["nonsense"])
```

Add `test_inner_tls_nests_inside_outer_tls_without_touching_the_wire`. Build a
tap the way the real relay does: two `socket.socketpair()`s and a pump thread
that copies bytes between them and records every byte. Wrap one end of each
pair in outer TLS (server on one side, client on the other, pinned by
fingerprint), then wrap both outer sockets with `wrap_inner_tls`. Send
`b"TOP-SECRET-INNER"` from the inner client and assert the inner server
receives it, that the tapped bytes are longer than the plaintext, and that
`b"TOP-SECRET-INNER"` does not appear in the tapped bytes. Finish by closing
the inner layers and calling `unwrap()` on both outer sockets; both unwraps
must succeed, which proves the outer TLS stream was never bypassed.

Also add `test_cloudmesh_node_relay_help_lists_serve` by running `python cloudmesh/node/cloudmesh_node.py relay --help` with `subprocess.run` and asserting `serve` and `init` in stdout.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cloudmesh/tests/test_relay_cli.py -q`
Expected: FAIL because `init_relay`, `open_outer_tls`, and `main` do not exist.

- [ ] **Step 3: Implement the TLS helper and CLI**

- `open_outer_tls`: with a CA file use `ssl.create_default_context(cafile=...)` and `server_hostname=host`; without a CA file use `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)`, `check_hostname=False`, `verify_mode=CERT_NONE`, then compare `der_fingerprint(sock.getpeercert(binary_form=True))` with the pinned value using `hmac.compare_digest`. Raise `RelayError("relay fingerprint is required")` when no CA file and no fingerprint are supplied, and `RelayError("relay identity mismatch")` on a mismatch. Close the socket before raising.
- `wrap_inner_tls` / `InnerTLSSocket`: never call `SSLContext.wrap_socket` on
  an `SSLSocket` — it reuses the raw file descriptor and bypasses the outer TLS
  layer, corrupting it. Use `ssl.MemoryBIO`: create `incoming`, `outgoing`,
  then `context.wrap_bio(incoming, outgoing, server_side=..., server_hostname=...)`.
  `InnerTLSSocket` exposes `recv(n)`, `sendall(data)`, `settimeout(seconds)`,
  `getpeercert(binary_form=True)`, `unwrap()`, and `close()`. Flush `outgoing`
  to the underlying socket under a lock after every write and before every raw
  read; feed raw reads into `incoming`. `recv` maps `SSLWantReadError` to a raw
  read and preserves `socket.timeout` by re-raising it, because
  `cloudmesh_node._recv_msg` relies on that exception to bound reads. The
  handshake runs in a `do_handshake()` loop that flushes on `SSLWantWriteError`
  and reads on `SSLWantReadError`. `getpeercert` returns the inner peer's DER.
  `unwrap()` first flushes, then unwraps the SSLObject and returns the outer
  socket with its TLS session intact.
- `admin_request`: open TLS, send the payload, read one frame, close, return the frame; translate socket/TLS errors into `RelayError("relay unreachable: ...")`.
- `init_relay`: generate the admin key (`secrets.token_hex(32)`); if `--tls-cert/--tls-key` are absent, generate `relay-cert.pem`/`relay-key.pem` next to the config; write `relay.json` with relative filenames; create the tokens file parent; return `{config, admin_key, tls_cert, tls_key, relay_fingerprint, controller_command, node_hint}`. Refuse to overwrite an existing config unless `--force` is added to the signature (add `force: bool = False`).
- `serve_relay`: load config, apply `bind`/`port` overrides, print `relay listening on host:port`, call `serve_forever()`.
- `main`: argparse with `init`, `serve`, `status`, `--config`, `--url`, `--bind`, `--port`, `--tls-cert`, `--tls-key`, `--force`. `status` loads the config and calls `admin_request` against `127.0.0.1:<port>`.
- In `cloudmesh_node.py::main`, add a `relay` subparser that calls `cloudmesh_relay.main(remaining_args)`. Use `parse_known_args` or a dedicated parser so `cloudmesh_node.py relay serve --config ...` passes through untouched.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest cloudmesh/tests/test_relay_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/node/cloudmesh_relay.py cloudmesh/node/cloudmesh_node.py cloudmesh/tests/test_relay_cli.py
git commit -m "feat: add standalone relay CLI and TLS client helper"
```

---

## Task 4: Controller relay stores and admin client

**Files:**
- Create: `cloudmesh/core/node_relay.py`
- Test: `cloudmesh/tests/test_node_relay_store.py`

**Interfaces:**
- Consumes: `cloudmesh.node.cloudmesh_relay` (`RelayError`, `open_outer_tls`, `admin_mac`, `send_frame`, `recv_frame`, `der_fingerprint`).
- Produces:
  - `RELAY_PROFILES_FILE = ".relays.json"`
  - `NODE_RELAY_FILE = ".node_relay.json"`
  - `DEFAULT_POOL = 4`
  - `class RelayProfileStore` with `load`, `get(url)`, `set(url, admin_key, relay_fingerprint, ca_file=None)`, `remove(url)`, `last_error`
  - `class NodeRelayStore` with `load`, `get(name)`, `set(name, entry)`, `remove(name)`, `names()`, `last_error`
  - `def split_relay_url(url: str) -> tuple[str, int]`
  - `class RelayAdminClient` with `enroll(relay_id, token, pool=4)`, `revoke(relay_id)`, `status()`, `ping()`
  - `class RelayTransport` with `connect() -> ssl.SSLSocket`

- [ ] **Step 1: Write the failing store and client tests**

```python
def test_profile_store_round_trip(tmp_path):
    store = node_relay.RelayProfileStore(tmp_path)
    store.set("relay.test:9997", "ab" * 32, "cd" * 32)
    assert store.get("relay.test:9997")["admin_key"] == "ab" * 32
    if os.name != "nt":
        assert (tmp_path / ".relays.json").stat().st_mode & 0o777 == 0o600


def test_corrupt_profile_store_is_a_named_error(tmp_path):
    (tmp_path / ".relays.json").write_text("{not json", encoding="utf-8")
    store = node_relay.RelayProfileStore(tmp_path)
    assert store.load() == {}
    assert "corrupt" in store.last_error.lower()


@pytest.mark.parametrize("url", ["relay.test", "relay.test:notaport", "[::1]"])
def test_relay_url_without_a_valid_port_is_a_named_error(url):
    with pytest.raises(node_relay.RelayError, match="host:port"):
        node_relay.split_relay_url(url)


def test_admin_client_enroll_and_revoke_against_a_real_relay(tmp_path):
    server = start_relay(tmp_path)
    client = node_relay.RelayAdminClient(
        f"127.0.0.1:{server.address[1]}", server.admin_key, server.fingerprint,
    )
    try:
        assert client.enroll("ab" * 16, "cd" * 32, pool=2)["data"]["success"] is True
        assert client.status()["type"] == "status"
        assert client.revoke("ab" * 16)["data"]["success"] is True
    finally:
        server.stop()


def test_admin_client_refuses_a_fingerprint_mismatch(tmp_path):
    server = start_relay(tmp_path)
    client = node_relay.RelayAdminClient(
        f"127.0.0.1:{server.address[1]}", server.admin_key, "00" * 32,
    )
    with pytest.raises(node_relay.RelayError, match="identity mismatch"):
        client.status()
    server.stop()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cloudmesh/tests/test_node_relay_store.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'cloudmesh.core.node_relay'`.

- [ ] **Step 3: Implement the stores and admin client**

- `split_relay_url`: accept `host:port`, `[v6]:port`; reject a missing/empty port, a non-integer port, and a bare IPv6 literal with `RelayError("relay URL must be host:port")`. Return `(host_without_brackets, int(port))`.
- Both stores: default base dir from `resolve_base_dir()`; `load()` returns `{}` and sets `last_error` on a non-object or invalid JSON; `set` writes atomically via the same pattern as `cloudmesh.core.drain`, `0600` on POSIX; `remove` returns whether the key existed and does not create the file when absent.
- `RelayAdminClient.__init__`: call `split_relay_url`; require a non-empty admin key and fingerprint. `_request` sends `{"type":"admin","action":...,"relay_id":...,"ts":...,"nonce":...,"mac":...}` through `open_outer_tls` and one `send_frame`/`recv_frame` pair. `enroll` includes `token` and `pool`; `revoke`, `status`, `ping` follow the spec.
- `RelayTransport.__init__(entry, profile, client_id, timeout=10)`: store `relay_id`, `url`, `relay_fingerprint`, `node_fingerprint`, admin key, CA file. `connect()` opens the outer TLS, sends `connect` with `connect_mac`, reads `paired`, builds an inner client context (`CERT_NONE`, `check_hostname=False`), calls `wrap_inner_tls(sock, context, server_side=False, server_hostname=relay_id)`, compares the inner peer certificate DER fingerprint with `hmac.compare_digest`, and returns the `InnerTLSSocket`. On any mismatch or handshake failure, close and raise `RelayError("relay node identity mismatch")` or `RelayError("relay inner TLS failed: ...")`.
- `RelayTransport` must send no application bytes before the fingerprint check succeeds.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest cloudmesh/tests/test_node_relay_store.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/core/node_relay.py cloudmesh/tests/test_node_relay_store.py
git commit -m "feat: add controller relay stores and admin client"
```

---

## Task 5: NodeClient relay transport

**Files:**
- Modify: `cloudmesh/core/node_client.py`
- Test: `cloudmesh/tests/test_node_client_relay.py`

**Interfaces:**
- Consumes: Task 4 `RelayTransport`, `NodeRelayStore`, `RelayProfileStore`.
- Produces:
  - `CLIENT_ID = secrets.token_hex(16)` module constant.
  - `NodeClient.__init__(..., transport="direct", relay_entry=None, relay_profile=None, relay_error=None, client_id=None)`
  - `NodeClient.from_config(node, name=None)`
  - `NodeClient._send_on_socket(sock, request, timeout) -> dict`
  - `NodeClient._send_relay(request, timeout) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
def test_from_config_without_a_name_stays_direct():
    client = NodeClient.from_config({"host": "127.0.0.1", "port": 1, "key": "k"})
    assert client.transport == "direct"


def test_from_config_with_a_relay_sidecar_selects_relay(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    NodeRelayStore(tmp_path).set("web-1", {
        "relay_id": "ab" * 16, "url": "relay.test:9997",
        "relay_fingerprint": "cd" * 32, "node_fingerprint": "ef" * 32,
    })
    RelayProfileStore(tmp_path).set("relay.test:9997", "11" * 32, "cd" * 32)

    client = NodeClient.from_config({"host": "relay.test", "port": 9997, "key": "k"}, name="web-1")

    assert client.transport == "relay"
    assert client.relay_entry["relay_id"] == "ab" * 16


def test_an_incomplete_relay_entry_returns_a_named_error(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    NodeRelayStore(tmp_path).set("web-1", {"relay_id": "ab" * 16})
    client = NodeClient.from_config({"host": "relay.test", "port": 9997, "key": "k"}, name="web-1")
    result = client.ping()
    assert result is False
    assert "relay config is incomplete" in client.last_error.lower()


def test_relay_execute_round_trip(tmp_path):
    relay_server, node_server = start_fake_relay_and_node(tmp_path)
    client = NodeClient("relay.test", 9997, "auth", transport="relay",
                        relay_entry=node_server.entry, relay_profile=relay_server.profile)
    try:
        assert client.execute("uptime")["stdout"].startswith("ok")
    finally:
        node_server.stop()
        relay_server.stop()
```

Add `test_no_application_bytes_are_sent_before_the_node_fingerprint_is_verified`: point the entry at a fake node with the wrong fingerprint, call `execute`, assert `client.last_error` contains `identity mismatch`, and assert the fake node received zero application bytes.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cloudmesh/tests/test_node_client_relay.py -q`
Expected: FAIL because `NodeClient` has no `transport` attribute.

- [ ] **Step 3: Implement relay transport in NodeClient**

- Add the new constructor parameters and `self.last_error = relay_error`.
- `from_config(node, name=None)`:
  - With no `name`, return the direct client exactly as today.
  - With a name, load `NodeRelayStore()`; if `last_error` is set, return a relay client with `relay_error="relay config is corrupt: ..."`.
  - If the name is absent from the store, return direct.
  - If the entry is missing `relay_id`, `url`, `relay_fingerprint`, or `node_fingerprint`, return a relay client with `relay_error="relay config is incomplete: missing ..."`.
  - Otherwise load the matching `RelayProfileStore` entry by `url`; if missing, `relay_error="relay profile is missing for <url>"`.
- Refactor the socket send/receive half of `_send` into `_send_on_socket(sock, request, timeout)`; `_send` keeps SPA and direct connect behavior.
- `_send_relay`: if `self.last_error`, return `{"type":"error","message": self.last_error, "request_sent": False}`. Otherwise create `RelayTransport`, connect, call `_send_on_socket`, and translate `RelayError` into `{"type":"error","message": str(exc), "request_sent": False}`. Close the socket in `finally`.
- `ping()` must remain `False` on error (it already checks `resp.get("type") == "pong"`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest cloudmesh/tests/test_node_client_relay.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/core/node_client.py cloudmesh/tests/test_node_client_relay.py
git commit -m "feat: route NodeClient requests through the relay"
```

---

## Task 6: Agent relay client and serve integration

**Files:**
- Modify: `cloudmesh/node/cloudmesh_node.py`
- Test: `cloudmesh/tests/test_agent_relay.py`

**Interfaces:**
- Consumes: Task 3 `open_outer_tls`; Task 2 relay.
- Produces:
  - `RELAY_CONFIG_FILE = BASE_DIR / ".node_relay.json"`
  - `def load_relay_config(path: Path) -> dict | None`
  - `class RelayClient` with `start()`, `stop()`, `status()`
  - `NodeAgent.__init__(..., relay_config=None, relay_only=False)`
  - `NodeAgent.serve()` starts the relay pool and skips the inbound listener when `relay_only` is true.
  - `NodeAgent.start_relay_only_for_test()` and `NodeAgent.stop_relay_for_test()`: test-facing wrappers that start and stop only the relay client, without entering the listener loop.
  - `NodeAgent.received_application_bytes() -> int`: test-facing counter of application bytes `_handle` has read (incremented as soon as a payload chunk arrives, before parsing). Used to prove a fingerprint mismatch never delivers the auth key.
  - `NodeAgent.info` includes `relay`: `{enabled, url, connected_slots, pool_size, last_error, last_connected_at}`.

- [ ] **Step 1: Write the failing agent tests**

```python
def test_agent_parks_the_configured_pool(tmp_path):
    relay_server = start_relay(tmp_path)
    config = node_config(relay_server, pool=2)
    agent = NodeAgent(port=0, auth_key="auth", bind_host="127.0.0.1", relay_config=config)
    agent.start_relay_only_for_test()
    try:
        assert wait_for(lambda: agent.relay_status()["connected_slots"] == 2)
    finally:
        agent.stop_relay_for_test()
        relay_server.stop()


def test_agent_replenishes_a_slot_after_pairing(tmp_path):
    relay_server = start_relay(tmp_path)
    config = node_config(relay_server, pool=2)
    agent = NodeAgent(port=0, auth_key="auth", bind_host="127.0.0.1", relay_config=config)
    agent.start_relay_only_for_test()
    client = NodeClient(... transport="relay", ...)
    try:
        assert client.ping() is True
        assert wait_for(lambda: agent.relay_status()["connected_slots"] == 2)
    finally:
        agent.stop_relay_for_test()
        relay_server.stop()


def test_relay_only_agent_does_not_open_the_direct_port(tmp_path):
    relay_server = start_relay(tmp_path)
    agent = NodeAgent(port=free_port(), auth_key="auth", bind_host="127.0.0.1",
                      relay_config=node_config(relay_server, pool=1), relay_only=True)
    thread = threading.Thread(target=agent.serve, daemon=True)
    thread.start()
    try:
        with pytest.raises(ConnectionRefusedError):
            socket.create_connection(("127.0.0.1", agent.port), timeout=0.5)
    finally:
        agent.stop()
        relay_server.stop()


def test_incomplete_relay_config_is_a_named_error(tmp_path):
    path = tmp_path / ".node_relay.json"
    path.write_text('{"relay_id": "ab"}', encoding="utf-8")
    with pytest.raises(ValueError, match="relay config is incomplete"):
        load_relay_config(path)


def test_agent_info_includes_relay_state(tmp_path):
    # start agent with a relay config and assert info["relay"]["enabled"] is True
    ...
```

Add `test_agent_reconnects_after_relay_restart`: start the relay on a fixed ephemeral port, start the agent, stop and restart the relay on the same port, and assert the pool returns to the configured size within 3 seconds.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cloudmesh/tests/test_agent_relay.py -q`
Expected: FAIL because `load_relay_config` and `relay_config` do not exist.

- [ ] **Step 3: Implement the relay client**

- `load_relay_config`: read JSON; require `relay_id` (32 hex), `url` (host:port), `node_token` (64 hex), `relay_fingerprint` (64 hex), `tls_cert`, `tls_key`, `pool` (1–32). Raise `ValueError("relay config is incomplete: <field>")` or `ValueError("relay config is corrupt: ...")` with names, never a bare `KeyError`.
- `RelayClient`: one daemon thread per slot plus a supervisor. Each slot loops:
  1. `open_outer_tls(host, port, relay_fingerprint, timeout=10)`.
  2. Send `register` with `register_mac(node_token, ...)`.
  3. Read `parked`; loop answering `ping` with `pong` and waiting for `paired`. A read timeout of 35 seconds means a missed keepalive; close and reconnect.
  4. On `paired` with `client_id`, build an inner server context from
     `tls_cert`/`tls_key` (raise and log if missing), call
     `wrap_inner_tls(sock, context, server_side=True)`, then
     `self.agent._handle(inner, ("relay", 0), client_id=client_id)`.
  5. Close and reconnect with exponential backoff 1 s → 60 s, ±20% jitter; reset the backoff after a successful registration.
- `start()` starts the supervisor; `stop()` sets a stop event, closes parked sockets, and joins threads for at most 2 seconds.
- `status()` returns the fields from the spec; `last_error` is the most recent error string and `last_connected_at` an ISO timestamp.
- `NodeAgent.__init__`: store `relay_config` and `relay_only`; build `RelayClient` only when a config is supplied.
- `serve()`: if `relay_config`, call `self._relay_client.start()` before the listener loop. If `relay_only`, skip creating the TCP listener entirely and sleep on the stop event instead.
- Add `--relay-config` and `--relay-only` to the `start` parser; `--relay-only` without `--relay-config` exits with a clear error.
- Add `stop`/`status` handling for the relay client so `cloudmesh_node.py stop` still works.
- `info` adds `relay` from `RelayClient.status()` or `{"enabled": False}`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest cloudmesh/tests/test_agent_relay.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/node/cloudmesh_node.py cloudmesh/tests/test_agent_relay.py
git commit -m "feat: add outbound relay client to the node agent"
```

---

## Task 7: Per-client limits in relay mode

**Files:**
- Modify: `cloudmesh/node/cloudmesh_node.py`
- Test: `cloudmesh/tests/test_agent_relay_limits.py`

**Interfaces:**
- Consumes: Task 6 `_handle(..., client_id=...)`.
- Produces:
  - `NodeAgent._handle(client, addr, client_id=None)`
  - `NodeAgent._relay_ddos` (`_StandaloneDDoSProtection(rate_max=120, conn_per_ip=8, ...)`)
  - `NodeAgent._rate_key(client_id, ip) -> str`

- [ ] **Step 1: Write the failing tests**

```python
def test_relay_requests_are_limited_per_client_id(agent):
    allowed = [agent._rate_key("ab" * 16, "relay") for _ in range(1)]
    assert allowed == ["relay:" + "ab" * 16]
    for _ in range(120):
        agent._relay_ddos.check_connection(allowed[0])
    ok, reason = agent._relay_ddos.check_connection(allowed[0])
    assert ok is False
    assert "rate" in reason.lower()


def test_one_client_ban_does_not_affect_another(agent):
    agent._relay_ddos.on_auth_failure("relay:" + "ab" * 16)
    assert agent._relay_ddos.check_connection("relay:" + "cd" * 16)[0] is True


def test_direct_mode_still_limits_per_ip(agent):
    for _ in range(30):
        agent._ddos.check_connection("203.0.113.5")
    assert agent._ddos.check_connection("203.0.113.5")[0] is False


def test_malformed_client_id_is_rejected_without_crashing(agent):
    with pytest.raises(ValueError):
        agent._rate_key("not-hex", "relay")
```

Add `test_auth_failure_bans_only_that_client`: call `_handle` with a wrong auth key and one `client_id`, then assert a second `client_id` is still allowed.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cloudmesh/tests/test_agent_relay_limits.py -q`
Expected: FAIL because `_rate_key` and `_relay_ddos` do not exist.

- [ ] **Step 3: Implement per-client limits**

- Add `self._relay_ddos = _StandaloneDDoSProtection(rate_max=120, rate_window=60, conn_per_ip=8, conn_total=64)` in `NodeAgent.__init__`.
- `_rate_key(client_id, ip)`: `client_id` must be 32 hex chars; return `f"relay:{client_id}"`. Without a client ID, return `ip`.
- `_handle`: choose `ddos = self._relay_ddos if client_id else self._ddos`, `key = self._rate_key(client_id, addr[0])`, and use `key` for `check_connection`, `on_auth_failure`, `on_auth_success`, `release_connection`, and the log lines. Direct mode behavior is unchanged.
- Log `AUTH_FAIL relay:<id>` instead of an IP when relayed. Never log the token.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest cloudmesh/tests/test_agent_relay_limits.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/node/cloudmesh_node.py cloudmesh/tests/test_agent_relay_limits.py
git commit -m "feat: rate-limit relay clients per client id"
```

---

## Task 8: `cm relay` controller commands

**Files:**
- Modify: `cloudmesh/main.py`
- Test: `cloudmesh/tests/test_relay_commands.py`

**Interfaces:**
- Consumes: Task 3 `init_relay`, `serve_relay`; Task 4 `RelayProfileStore`, `RelayAdminClient`.
- Produces:
  - `def cmd_relay_init(args)`
  - `def cmd_relay_add(args)`
  - `def cmd_relay_serve(args)`
  - `def cmd_relay_status(args)`
  - `def cmd_relay_revoke(args)`
  - Parser: `relay init|add|serve|status|revoke`, dispatch in `cmds`.

- [ ] **Step 1: Write the failing command tests**

```python
def test_relay_init_writes_a_profile_and_prints_commands(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    args = Namespace(url="relay.example.com:9997", config=str(tmp_path / "relay.json"),
                     bind="0.0.0.0", port=9997, tls_cert=None, tls_key=None, force=False)
    main_module.cmd_relay_init(args)
    output = capsys.readouterr().out
    assert "cm relay add" in output
    assert (tmp_path / "relay.json").is_file()


def test_relay_add_stores_the_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    main_module.cmd_relay_add(Namespace(url="relay.test:9997", key="ab" * 32,
                                        fingerprint="cd" * 32, ca_file=None))
    assert RelayProfileStore(tmp_path).get("relay.test:9997")["admin_key"] == "ab" * 32


def test_relay_status_uses_the_admin_client(monkeypatch, capsys):
    class FakeClient:
        def __init__(self, *a, **k): pass
        def status(self): return {"type": "status", "data": {"totals": {"parked": 2}}}
    monkeypatch.setattr(main_module, "RelayAdminClient", FakeClient)
    main_module.cmd_relay_status(Namespace(relay="relay.test:9997"))
    assert "parked" in capsys.readouterr().out


def test_relay_revoke_uses_the_node_sidecar(monkeypatch):
    calls = []
    class FakeClient:
        def __init__(self, *a, **k): pass
        def revoke(self, relay_id): calls.append(relay_id); return {"data": {"success": True}}
    monkeypatch.setattr(main_module, "RelayAdminClient", FakeClient)
    monkeypatch.setattr(main_module, "NodeRelayStore", lambda: FakeNodeStore())
    main_module.cmd_relay_revoke(Namespace(name="web-1", relay="relay.test:9997"))
    assert calls == ["ab" * 16]


def test_relay_parser_wires_every_subcommand():
    parser = main_module.build_parser()
    for argv in (["relay", "init"], ["relay", "add", "--url", "h:1", "--key", "k"],
                 ["relay", "serve"], ["relay", "status"], ["relay", "revoke", "-n", "n"]):
        assert parser.parse_args(argv).action
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cloudmesh/tests/test_relay_commands.py -q`
Expected: FAIL with `AttributeError: module ... has no attribute 'cmd_relay_init'`.

- [ ] **Step 3: Implement the relay commands**

- Add the parser block next to the `node` parser:
  ```
  relay = subparsers.add_parser("relay", help="Manage relay servers")
  relay_sub = relay.add_subparsers(dest="action")
  init_p = relay_sub.add_parser("init")  # --url --config --bind --port --tls-cert --tls-key --force
  add_p = relay_sub.add_parser("add")    # --url --key --fingerprint --ca-file
  serve_p = relay_sub.add_parser("serve")  # --config --bind --port
  status_p = relay_sub.add_parser("status")  # --relay
  revoke_p = relay_sub.add_parser("revoke")  # -n --relay
  ```
- `cmd_relay_init`: call `init_relay(Path(args.config or "relay.json"), ...)`; print the admin key once, the relay fingerprint, the `cm relay add` command, and the `cm node relay enable` hint.
- `cmd_relay_add`: `RelayProfileStore().set(...)`; print `Relay profile saved for <url>`.
- `cmd_relay_serve`: call `serve_relay(Path(args.config or "relay.json"), bind=args.bind, port=args.port)`.
- `cmd_relay_status`: resolve `args.relay` (or the only profile if omitted); build `RelayAdminClient`; print uptime, totals, and per-node parked/paired counts; on `RelayError` print the named error and `raise SystemExit(1)`.
- `cmd_relay_revoke`: load the node sidecar by `args.name`; require a relay entry; call `client.revoke(relay_id)`; print the result. Do not delete the controller sidecar (the node may still be configured; `cm node relay disable` removes it).
- Add `"relay": lambda: {...}.get(args.action, lambda _a: relay.print_help())(args)` to `cmds`.
- Ensure `main_module.build_parser()` exists; if the parser is currently built inside `main()`, extract it into `build_parser()` without changing behavior.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest cloudmesh/tests/test_relay_commands.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/main.py cloudmesh/tests/test_relay_commands.py
git commit -m "feat: add cm relay controller commands"
```

---

## Task 9: Relay bootstrap over SSH and local mode

**Files:**
- Modify: `cloudmesh/core/node_relay.py`
- Test: `cloudmesh/tests/test_relay_bootstrap.py`

**Interfaces:**
- Consumes: Task 4 stores, `RelayAdminClient`; Task 1 `generate_self_signed_cert`, `cert_fingerprint`.
- Produces:
  - `class SSHRunner` protocol with `run(host, user, key, command, port=22, timeout=30) -> tuple[str, int]` and `upload_bytes(host, user, key, remote_path, data, mode=0o600, port=22) -> None`
  - `class ParamikoSSHRunner`
  - `def restart_agent(runner, host, user, key, port=22) -> tuple[bool, str]`
  - `class RelayProvisioner` with `enable_ssh`, `enable_local`, `import_local`, `disable_ssh`, `disable_local`

- [ ] **Step 1: Write the failing bootstrap tests**

```python
class FakeSSH:
    def __init__(self, fail_upload=False, fail_run=False):
        self.files = {}
        self.commands = []
        self.fail_upload = fail_upload
        self.fail_run = fail_run

    def run(self, host, user, key, command, port=22, timeout=30):
        self.commands.append(command)
        if self.fail_run:
            return ("boom", 1)
        if "systemctl" in command:
            return ("", 0)
        return ("", 0)

    def upload_bytes(self, host, user, key, remote_path, data, mode=0o600, port=22):
        if self.fail_upload:
            raise OSError("upload failed")
        self.files[remote_path] = (data, mode)


def test_enable_ssh_uploads_private_files_and_saves_sidecar(tmp_path, monkeypatch):
    ssh = FakeSSH()
    provisioner, stores = make_provisioner(tmp_path, ssh)
    result = provisioner.enable_ssh(
        "web-1", "relay.test:9997", ssh_host="10.0.0.5", ssh_user="root",
        verify=lambda name, entry: True,
    )
    assert result["relay_id"]
    assert any(path.endswith("relay-key.pem") for path in ssh.files)
    assert all(mode == 0o600 for _, mode in ssh.files.values())
    assert stores.nodes.get("web-1")["relay_id"] == result["relay_id"]


def test_enable_ssh_rolls_back_on_upload_failure(tmp_path):
    ssh = FakeSSH(fail_upload=True)
    provisioner, stores = make_provisioner(tmp_path, ssh)
    with pytest.raises(RelayError, match="upload failed"):
        provisioner.enable_ssh("web-1", "relay.test:9997", ssh_host="10.0.0.5",
                               ssh_user="root", verify=lambda *a: True)
    assert stores.nodes.get("web-1") is None


def test_restart_command_prefers_systemd_then_rcd_then_service(tmp_path):
    ssh = FakeSSH()
    assert restart_agent(ssh, "h", "u", None) == (True, "systemctl restart cloudmesh-node")
    ssh2 = FakeSSH(); ssh2.run = lambda *a, **k: ("not found", 1)
    assert "rc.d" in restart_agent(ssh2, "h", "u", None)[1]


def test_enable_local_writes_node_config_and_returns_import(tmp_path):
    provisioner, _ = make_provisioner(tmp_path, FakeSSH())
    result = provisioner.enable_local("web-1", "relay.test:9997", pool=2)
    node_file = tmp_path / ".cloudmesh-node" / ".node_relay.json"
    assert json.loads(node_file.read_text())["pool"] == 2
    assert result["import_command"].startswith("cm node relay import")


def test_import_local_enrolls_and_saves_the_sidecar(tmp_path):
    provisioner, stores = make_provisioner(tmp_path, FakeSSH())
    provisioner.import_local("web-1", "relay.test:9997", "ab" * 16, "cd" * 32,
                             "ef" * 32, "11" * 32)
    assert stores.nodes.get("web-1")["node_fingerprint"] == "ef" * 32


def test_disable_local_removes_the_node_config(tmp_path):
    provisioner, _ = make_provisioner(tmp_path, FakeSSH())
    provisioner.enable_local("web-1", "relay.test:9997")
    provisioner.disable_local("web-1", "relay.test:9997")
    assert not (tmp_path / ".cloudmesh-node" / ".node_relay.json").exists()
```

Add `test_enable_ssh_rolls_back_on_verification_failure` and `test_enable_ssh_prints_a_manual_restart_when_no_unit_exists`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cloudmesh/tests/test_relay_bootstrap.py -q`
Expected: FAIL because `RelayProvisioner` and `SSHRunner` do not exist.

- [ ] **Step 3: Implement bootstrap**

- `ParamikoSSHRunner`: one `SSHClient` per call; `RejectPolicy`; load `~/.ssh/known_hosts` when it exists; `connect(hostname, port, username, key_filename=key, timeout=10)`; `run` uses `exec_command` with `recv_exit_status`; `upload_bytes` uses `open_sftp().putfo` and `chmod(mode)` on POSIX. Translate `paramiko` exceptions into `RelayError`.
- `restart_agent`: probe `command -v systemctl`; if exit 0, `systemctl restart cloudmesh-node`; else probe `command -v service`; if exit 0, `service cloudmesh-node restart`; else probe `/usr/local/etc/rc.d/cloudmesh_node` and `/etc/rc.d/cloudmesh_node`, run `<path> restart`; else run `~/.cloudmesh-node/restart.sh`; if that fails, return `(False, "no service manager found; run ~/.cloudmesh-node/start.sh")`. Return `(True, command)` on success.
- `RelayProvisioner.__init__(profiles, nodes, ssh=None, base_dir=None, admin_client_factory=RelayAdminClient)`. Default `ssh=ParamikoSSHRunner()`.
- `enable_ssh`:
  1. Load the relay profile; raise `RelayError("relay profile not found")` if absent.
  2. Generate `relay_id = token_hex(16)`, `token = token_hex(32)`, and a cert/key if not supplied.
  3. Build the node config object; serialize it.
  4. Upload `relay-cert.pem` (`0644`), `relay-key.pem` (`0600`), and `.node_relay.json` (`0600`) to `~/.cloudmesh-node/`.
  5. Enroll at the relay; save the controller sidecar.
  6. Restart the agent; if restart fails, keep the config but return `restart_ok=False` and the manual command.
  7. Verify with the injected `verify` callback or a `NodeClient` ping. The
     agent needs a moment to restart and re-park its pool, so retry the
     verification every 0.5 s for up to 15 s before declaring failure. On
     failure, revoke and remove the sidecar, then raise `RelayError`.
- `enable_local`: generate the same material under `base_dir/.cloudmesh-node` (default `Path.home()/".cloudmesh-node"`), write `.node_relay.json`, and return `{relay_id, token, node_fingerprint, relay_fingerprint, import_command}`. Do not contact the relay.
- `import_local`: save the controller sidecar and enroll the token at the relay. Use the profile for the URL.
- `disable_ssh`: remove the node config and key files over SSH, restart, revoke the token, and remove the controller sidecar. `disable_local`: remove the node config and return the revoke hint.
- Every failure path leaves no half-written file: write to a temp name, `os.replace`, and `chmod`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest cloudmesh/tests/test_relay_bootstrap.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/core/node_relay.py cloudmesh/tests/test_relay_bootstrap.py
git commit -m "feat: add relay bootstrap over SSH and local mode"
```

---

## Task 10: Node CLI wiring and transport-aware commands

**Files:**
- Modify: `cloudmesh/main.py`
- Test: `cloudmesh/tests/test_node_relay_commands.py`

**Interfaces:**
- Consumes: Task 9 `RelayProvisioner`, Task 4 stores.
- Produces:
  - `cmd_node_relay(args)` with `args.relay_action` in `enable`, `import`, `disable`, `status`.
  - `cm node add --relay --ssh-host --ssh-user ...`
  - `cm node list` adds a `Transport` column.
  - Every `NodeClient.from_config(info)` call with a node name in scope passes `name=name`. Call sites: `cmd_node_gpu`, `cmd_node_job` (four), `cmd_node_list_cloud`, `cmd_node_test`, `cmd_node_info_cloud`, `cmd_node_monitor`, `cmd_node_exec`, `run_on_node`, `cmd_watch`, `cmd_node_dashboard`, `cmd_weather`, `cmd_job_checkpoint`, `features.ping_all`, `features.generate_report`, `gossip.scan_all`, `panic.execute_panic`, `panic.rotate_node_keys`, `panic.retry_pending`, `task_queue._client`.

- [ ] **Step 1: Write the failing CLI tests**

```python
def test_node_relay_enable_requires_ssh_or_local(monkeypatch):
    args = Namespace(name="web-1", relay="relay.test:9997", ssh_host=None,
                     ssh_user=None, ssh_key=None, ssh_port=22, local=False,
                     pool=4, cert=None, key=None)
    with pytest.raises(SystemExit) as exc:
        main_module.cmd_node_relay(args)
    assert exc.value.code == 2


def test_node_relay_import_writes_the_sidecar(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    args = Namespace(relay_action="import", name="web-1", relay="relay.test:9997",
                     relay_id="ab" * 16, token="cd" * 32,
                     node_fingerprint="ef" * 32, relay_fingerprint="11" * 32)
    main_module.cmd_node_relay(args)
    assert NodeRelayStore(tmp_path).get("web-1")["relay_id"] == "ab" * 16


def test_node_add_with_relay_rolls_back_on_enable_failure(monkeypatch):
    # provisioner raises; assert the keyring entry is gone
    ...


def test_node_list_shows_relay_transport(tmp_path, monkeypatch, capsys):
    # keyring has web-1 and web-2; sidecar only for web-1; assert "RELAY" and "DIRECT"
    ...


def test_node_commands_pass_the_node_name(monkeypatch):
    seen = []
    monkeypatch.setattr(main_module.NodeClient, "from_config",
                        classmethod(lambda cls, info, name=None: seen.append(name) or FakeClient()))
    main_module.cmd_node_test(Namespace(name="web-1"))
    assert seen == ["web-1"]
```

Add `test_node_relay_disable_revokes_and_removes_the_sidecar` and `test_node_relay_status_prints_the_relay_block`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cloudmesh/tests/test_node_relay_commands.py -q`
Expected: FAIL because `cmd_node_relay` and the parser flags do not exist.

- [ ] **Step 3: Implement the node CLI**

- Add `node relay` with `relay_sub = relay_p.add_subparsers(dest="relay_action")`:
  - `enable`: `-n`, `--relay`, `--ssh-host`, `--ssh-user`, `--ssh-key`, `--ssh-port`, `--local`, `--pool`, `--cert`, `--key`.
  - `import`: `-n`, `--relay`, `--relay-id`, `--token`, `--node-fingerprint`, `--relay-fingerprint`.
  - `disable`: `-n`, `--ssh-host`, `--ssh-user`, `--ssh-key`, `--ssh-port`, `--local`.
  - `status`: `-n`.
- `cmd_node_relay`: dispatch on `args.relay_action`; print the provisioner result; on `RelayError` print the message and `raise SystemExit(1)`.
- `cmd_node_relay_enable`: require exactly one of `--local` and `--ssh-user`; if SSH mode and `--ssh-host` is missing, use the keyring host only when the record is not relay-backed; otherwise `raise SystemExit(2)`.
- `cm node add`: make `-H/--host` optional in the parser, validate `host or relay`, add `--relay`, `--ssh-host`, `--ssh-user`, `--ssh-key`, `--ssh-port`, `--pool`. When `--relay` is set, store `{host: relay_host, port: relay_port, key: auth_key}` and call `RelayProvisioner.enable_ssh`; on failure remove the keyring entry and re-raise as a printed error + `SystemExit(1)`.
- `cmd_node_list_cloud`: add `Transport`; `relay_names = NodeRelayStore().names()`; `"RELAY"` if name in relay_names else `"DIRECT"`.
- Pass `name=name` at every listed call site. For `task_queue._client(node)`, use `NodeClient.from_config(info, name=node)`.
- `cmd_node_test`, `cmd_node_info_cloud`, `cmd_node_exec` print `client.last_error` when set, instead of a generic offline message.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest cloudmesh/tests/test_node_relay_commands.py -q`
Expected: PASS. Then run the affected existing tests: `python -m pytest cloudmesh/tests/test_cli.py cloudmesh/tests/test_task_queue.py cloudmesh/tests/test_node_drain.py -q`.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/main.py cloudmesh/tests/test_node_relay_commands.py
git commit -m "feat: wire relay commands into the node CLI"
```

---

## Task 11: Doctor rows, installer, and docs

**Files:**
- Modify: `cloudmesh/main.py`
- Modify: `cloudmesh/node/node-install.sh`
- Modify: `README.md`, `SECURITY.md`, `docs/UPGRADING.md`, `docs/LTS.md`, `CHANGELOG.md`
- Test: `cloudmesh/tests/test_relay_doctor.py`, `cloudmesh/tests/test_installers.py`

**Interfaces:**
- Consumes: Task 4 stores, Task 1 `cert_fingerprint`; Task 8/10 commands.
- Produces:
  - Doctor rows: `Relay profile`, `Node relay config`, `Relay certificate`, `Node certificate`, `Relay fingerprint`, `Relay reachable`.
  - Installer copies `cloudmesh_relay.py` when it sits next to `cloudmesh_node.py`; a relay-configured node that lacks the module fails with a clear message.
  - README section "Nodes behind NAT (relay)" with the topology diagram and the four-command workflow.

- [ ] **Step 1: Write the failing tests**

```python
def test_doctor_reports_relay_profile_and_node_config(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    RelayProfileStore(tmp_path).set("relay.test:9997", "ab" * 32, "cd" * 32)
    NodeRelayStore(tmp_path).set("web-1", {
        "relay_id": "ab" * 16, "url": "relay.test:9997",
        "relay_fingerprint": "cd" * 32, "node_fingerprint": "ef" * 32,
    })
    main_module.cmd_doctor(Namespace(base_dir=str(tmp_path)))
    output = capsys.readouterr().out
    assert "Relay profile" in output
    assert "Node relay config" in output


def test_doctor_warns_when_a_configured_relay_is_unreachable(tmp_path, monkeypatch, capsys):
    # profile points at 127.0.0.1:1; assert the row is present and the command does not raise
    ...


def test_installer_copies_the_relay_module():
    text = Path("cloudmesh/node/node-install.sh").read_text(encoding="utf-8")
    assert "cloudmesh_relay.py" in text
```

Add `test_readme_documents_the_relay_workflow` asserting `cm relay init`, `cm node relay enable`, and "relay" appear in `README.md`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cloudmesh/tests/test_relay_doctor.py cloudmesh/tests/test_installers.py -q`
Expected: FAIL because the doctor rows and installer copy do not exist.

- [ ] **Step 3: Implement the doctor rows and installer copy**

- `cmd_doctor`: after the node checks, add:
  - `Relay profile`: warn if no profile is configured; pass if `.relays.json` loads.
  - `Node relay config`: warn if no node sidecar; fail if `last_error`.
  - `Relay certificate` / `Node certificate`: fail if a configured path is missing or expired; warn inside 30 days.
  - `Relay fingerprint`: fail if the stored fingerprint is not 64 hex chars.
  - `Relay reachable`: a 1-second `RelayAdminClient.ping()`; warn only when a profile is configured.
- Installer: after copying `cloudmesh_node.py`, copy `cloudmesh_relay.py` from `SCRIPT_DIR` when it exists; do not fail the install when it is absent (direct-only installs still work). When `.node_relay.json` exists and the module is missing, `start.sh` prints `relay module not installed; direct mode only`.
- README: add the topology diagram from the spec, the four commands, the local-mode fallback, and the Phase 1 limitations (no node-to-node, no multi-controller).
- SECURITY.md: add the two-leg TLS model, the fingerprint pinning, the token exposure note, and the relay's availability-only trust.
- UPGRADING/LTS/CHANGELOG: note 4.3.0 and the new commands.
- Do not bump the version in this task; Task 12 does the release surfaces after acceptance.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest cloudmesh/tests/test_relay_doctor.py cloudmesh/tests/test_installers.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/main.py cloudmesh/node/node-install.sh README.md SECURITY.md docs/UPGRADING.md docs/LTS.md CHANGELOG.md cloudmesh/tests/test_relay_doctor.py cloudmesh/tests/test_installers.py
git commit -m "docs: document relay mode and add doctor checks"
```

---

## Task 12: End-to-end acceptance and release surfaces

**Files:**
- Create: `cloudmesh/tests/test_relay_e2e.py`
- Modify: `pyproject.toml` and every version surface listed by `test_release_metadata.py`
- Test: `cloudmesh/tests/test_relay_e2e.py`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: the acceptance evidence and the 4.3.0 version bump.

- [ ] **Step 1: Write the end-to-end tests**

```python
def test_execute_info_upload_and_job_through_the_relay(tmp_path):
    relay_server, agent, client = start_full_stack(tmp_path)
    try:
        assert client.ping() is True
        assert client.execute("echo relay-ok")["stdout"].strip() == "relay-ok"
        assert client.get_info()["hostname"]
        assert client.upload_file("data/note.txt", "hello")["success"] is True
        assert client.download_file("data/note.txt")["content"] == "hello"
        job = client.start_job("echo done")
        assert wait_for(lambda: client.check_job(job["job_id"])["status"] == "completed")
    finally:
        stop_full_stack(relay_server, agent)


def test_relay_capture_contains_no_plaintext(tmp_path):
    relay_server, agent, client = start_full_stack(tmp_path, capture=True)
    try:
        client.execute("echo TOP-SECRET-OUTPUT")
        captured = relay_server.captured_bytes()
        assert b"TOP-SECRET-OUTPUT" not in captured
        assert b"echo TOP-SECRET-OUTPUT" not in captured
        assert b"auth" not in captured
    finally:
        stop_full_stack(relay_server, agent)


def test_relay_restart_keeps_the_node_usable(tmp_path):
    relay_server, agent, client = start_full_stack(tmp_path)
    relay_server.stop()
    relay_server = restart_on_same_port(relay_server)
    try:
        assert wait_for(client.ping, timeout=3)
    finally:
        stop_full_stack(relay_server, agent)


def test_wrong_node_certificate_never_receives_the_auth_key(tmp_path):
    relay_server, agent, client = start_full_stack(tmp_path, wrong_fingerprint=True)
    try:
        assert client.execute("id")["message"].lower().startswith("relay node identity mismatch")
        assert b"auth" not in agent.received_application_bytes()
    finally:
        stop_full_stack(relay_server, agent)


def test_revoked_token_cannot_re-register(tmp_path):
    relay_server, agent, client = start_full_stack(tmp_path)
    try:
        relay_server.revoke(agent.relay_id)
        assert wait_for(lambda: agent.relay_status()["last_error"] is not None, timeout=3)
    finally:
        stop_full_stack(relay_server, agent)
```

- [ ] **Step 2: Run the tests to verify they fail for the right reason**

Run: `python -m pytest cloudmesh/tests/test_relay_e2e.py -q`
Expected: FAIL only if a previous task is incomplete; if all previous tasks are done, the tests should pass on the first run. If they fail, fix the owning task, not the test.

- [ ] **Step 3: Run the full verification**

Run: `python -m pytest cloudmesh/tests -q`
Expected: PASS with the existing suite plus the new relay tests.

Run: `python -m pytest cloudmesh/tests --cov=cloudmesh --cov-report=term-missing -q`
Expected: total coverage ≥ 45%.

- [ ] **Step 4: Bump the version surfaces**

Update `pyproject.toml` and every surface checked by `cloudmesh/tests/test_release_metadata.py` to `4.3.0`. Run:

`python -m pytest cloudmesh/tests/test_release_metadata.py cloudmesh/tests/test_release_integrity.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cloudmesh/tests/test_relay_e2e.py pyproject.toml
git commit -m "test: add relay end-to-end acceptance and bump to 4.3.0"
```

---

## Self-Review Notes

- **Spec coverage:** Goals G1–G6 map to Tasks 2–10. Non-goals are enforced by the absence of node-to-node actions and by Task 10's direct-mode regression tests. The failure table maps to Tasks 2, 4, 5, 6, 9, and 12. Observability maps to Task 11.
- **Known implementation order:** Task 3 introduces `open_outer_tls`, which Task 2's tests may import. If Task 2 is implemented first, use a local `ssl` helper in its tests and switch to `open_outer_tls` in Task 3. The production code order is 1 → 2 → 3.
- **No task writes product code before its test.** Every task starts with a failing test and ends with a full-suite run.
- **Type consistency:** `relay_id` is always 32 hex chars; `token` and fingerprints are 64 hex chars; `client_id` is 32 hex chars; `pool` is an integer 1–32. These values appear identically in Tasks 1–12.
