import json
import os
import secrets
import select
import socket
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from cloudmesh.node import cloudmesh_relay as relay

ADMIN_KEY = "11" * 32


def now():
    return int(time.time())


def start_relay_with_config(tmp_path):
    cert, key = tmp_path / "relay-cert.pem", tmp_path / "relay-key.pem"
    relay.generate_self_signed_cert(cert, key, "relay.test")
    config = relay.RelayConfig(
        bind="127.0.0.1",
        port=0,
        admin_key=ADMIN_KEY,
        tls_cert=str(cert),
        tls_key=str(key),
        tokens_file=str(tmp_path / "tokens.json"),
    )
    config_path = tmp_path / "relay.json"
    config.save(config_path)
    server = relay.RelayServer(config, pair_timeout=0.2)
    server.start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, config_path, server.fingerprint


def test_init_writes_a_private_config_and_certificate(tmp_path):
    config_path = tmp_path / "relay.json"
    result = relay.init_relay(config_path, url="relay.example.com:9997")
    data = json.loads(config_path.read_text())

    assert data["port"] == 9997
    assert data["admin_key"] == result["admin_key"]
    assert Path(result["tls_cert"]).is_file()
    assert Path(result["tls_key"]).is_file()
    assert len(result["relay_fingerprint"]) == 64
    assert result["relay_fingerprint"] == relay.cert_fingerprint(result["tls_cert"])
    if os.name != "nt":
        assert (config_path.stat().st_mode & 0o777) == 0o600
        assert (Path(result["tls_key"]).stat().st_mode & 0o777) == 0o600


def test_init_refuses_to_overwrite_without_force(tmp_path):
    config_path = tmp_path / "relay.json"
    relay.init_relay(config_path)
    with pytest.raises(relay.RelayError, match="already exists"):
        relay.init_relay(config_path)


def test_serve_refuses_missing_certificate(tmp_path):
    config_path = tmp_path / "relay.json"
    relay.init_relay(config_path)
    config = json.loads(config_path.read_text())
    (config_path.parent / config["tls_cert"]).unlink()

    with pytest.raises(relay.RelayError):
        relay.serve_relay(config_path)


def test_status_reads_a_running_relay(tmp_path):
    server, _config_path, fingerprint = start_relay_with_config(tmp_path)
    try:
        ts = now()
        nonce = secrets.token_hex(8)
        result = relay.admin_request(
            "127.0.0.1",
            server.address[1],
            server.admin_key,
            fingerprint,
            {
                "type": "admin",
                "action": "status",
                "relay_id": "",
                "ts": ts,
                "nonce": nonce,
                "mac": relay.admin_mac(server.admin_key, "status", "", ts, nonce),
            },
        )
        assert result["type"] == "status"
    finally:
        server.stop()


def test_open_outer_tls_rejects_an_identity_mismatch(tmp_path):
    server, _config_path, _fingerprint = start_relay_with_config(tmp_path)
    try:
        with pytest.raises(relay.RelayError, match="identity mismatch"):
            relay.open_outer_tls("127.0.0.1", server.address[1], "00" * 32)
    finally:
        server.stop()


def test_open_outer_tls_requires_a_fingerprint_or_ca_file():
    with pytest.raises(relay.RelayError, match="fingerprint is required"):
        relay.open_outer_tls("127.0.0.1", 1, None)


def test_main_help_lists_init_and_serve(capsys):
    with pytest.raises(SystemExit) as exc:
        relay.main(["--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "init" in output
    assert "serve" in output


def test_main_rejects_an_unknown_subcommand(capsys):
    with pytest.raises(SystemExit):
        relay.main(["nonsense"])


def test_inner_tls_nests_inside_outer_tls_without_touching_the_wire(tmp_path):
    relay_cert, relay_key = tmp_path / "relay-cert.pem", tmp_path / "relay-key.pem"
    relay.generate_self_signed_cert(relay_cert, relay_key, "relay.test")
    node_cert, node_key = tmp_path / "node-cert.pem", tmp_path / "node-key.pem"
    node_fingerprint = relay.generate_self_signed_cert(node_cert, node_key, "node-1")

    client_raw, tap_client = socket.socketpair()
    tap_server, server_raw = socket.socketpair()
    captured = bytearray()
    stop = threading.Event()

    def pump():
        sources = [tap_client, tap_server]
        while not stop.is_set():
            readable, _, _ = select.select(sources, [], [], 0.05)
            for source in readable:
                try:
                    data = source.recv(65536)
                except OSError:
                    return
                if not data:
                    return
                captured.extend(data)
                target = tap_server if source is tap_client else tap_client
                try:
                    target.sendall(data)
                except OSError:
                    return

    pump_thread = threading.Thread(target=pump, daemon=True)
    pump_thread.start()

    outer_server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    outer_server_context.load_cert_chain(relay_cert, relay_key)
    outer_client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    outer_client_context.check_hostname = False
    outer_client_context.verify_mode = ssl.CERT_NONE

    outer = {}

    def build_outer_server():
        outer["server"] = outer_server_context.wrap_socket(server_raw, server_side=True)

    outer_thread = threading.Thread(target=build_outer_server)
    outer_thread.start()
    outer_client = outer_client_context.wrap_socket(client_raw, server_hostname="relay.test")
    outer_thread.join(2)
    outer_server = outer["server"]

    inner_server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    inner_server_context.load_cert_chain(node_cert, node_key)
    inner_client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    inner_client_context.check_hostname = False
    inner_client_context.verify_mode = ssl.CERT_NONE

    inner = {}

    def build_inner_server():
        inner["server"] = relay.wrap_inner_tls(
            outer_server, inner_server_context, server_side=True
        )

    inner_thread = threading.Thread(target=build_inner_server)
    inner_thread.start()
    inner_client = relay.wrap_inner_tls(
        outer_client,
        inner_client_context,
        server_side=False,
        server_hostname="node-1",
    )
    inner_thread.join(2)
    inner_server = inner["server"]

    try:
        payload = b"TOP-SECRET-INNER"
        inner_client.sendall(payload)
        assert inner_server.recv(len(payload)) == payload
        assert relay.der_fingerprint(
            inner_client.getpeercert(binary_form=True)
        ) == node_fingerprint

        outer_client.sendall(b"outer-still-alive")
        assert outer_server.recv(len(b"outer-still-alive")) == b"outer-still-alive"

        tapped = bytes(captured)
        assert len(tapped) > len(payload)
        assert payload not in tapped
        assert b"outer-still-alive" not in tapped

        assert inner_client.unwrap() is outer_client
        assert inner_server.unwrap() is outer_server
    finally:
        stop.set()
        for item in (inner_client, inner_server, outer_client, outer_server):
            try:
                item.close()
            except OSError:
                pass
        tap_client.close()
        tap_server.close()


def test_cloudmesh_node_relay_help_lists_serve():
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, str(root / "node" / "cloudmesh_node.py"), "relay", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0
    assert "serve" in result.stdout
    assert "init" in result.stdout
