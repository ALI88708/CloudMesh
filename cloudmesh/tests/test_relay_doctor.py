import json
from argparse import Namespace
from pathlib import Path

from cloudmesh.core.node_relay import NodeRelayStore, RelayProfileStore
from cloudmesh.node import cloudmesh_relay as relay

import cloudmesh.main as main_module

ROOT = Path(__file__).resolve().parents[2]
RELAY_URL = "relay.test:9997"
ADMIN_KEY = "ab" * 32
RELAY_FP = "cd" * 32
NODE_ENTRY = {
    "relay_id": "ab" * 16,
    "url": RELAY_URL,
    "relay_fingerprint": RELAY_FP,
    "node_fingerprint": "ef" * 32,
}


def doctor(tmp_path):
    main_module.cmd_doctor(Namespace(base_dir=str(tmp_path)))


def test_doctor_reports_relay_profile_and_node_config(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    RelayProfileStore(tmp_path).set(RELAY_URL, ADMIN_KEY, RELAY_FP)
    NodeRelayStore(tmp_path).set("web-1", NODE_ENTRY)
    doctor(tmp_path)
    output = capsys.readouterr().out
    assert "Relay profile" in output
    assert "Node relay config" in output


def test_doctor_warns_when_a_configured_relay_is_unreachable(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    RelayProfileStore(tmp_path).set("127.0.0.1:1", ADMIN_KEY, RELAY_FP)
    doctor(tmp_path)
    output = capsys.readouterr().out
    assert "Relay reachable" in output
    assert "WARN" in output or "FAIL" in output


def test_doctor_fails_a_malformed_stored_fingerprint(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    (tmp_path / ".relays.json").write_text(
        json.dumps(
            {
                RELAY_URL: {
                    "admin_key": ADMIN_KEY,
                    "relay_fingerprint": "not-a-fingerprint",
                    "ca_file": None,
                }
            }
        ),
        encoding="utf-8",
    )
    doctor(tmp_path)
    output = capsys.readouterr().out
    assert "Relay fingerprint" in output
    assert "FAIL" in output


def test_doctor_fails_an_expired_node_certificate(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    node_dir = tmp_path / ".cloudmesh-node"
    node_dir.mkdir()
    relay.generate_self_signed_cert(
        node_dir / "relay-cert.pem", node_dir / "relay-key.pem", "web-1", days=0
    )
    NodeRelayStore(tmp_path).set("web-1", NODE_ENTRY)
    doctor(tmp_path)
    output = capsys.readouterr().out
    assert "Node certificate" in output
    assert "expired" in output


def test_doctor_warns_about_a_certificate_expiring_soon(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    node_dir = tmp_path / ".cloudmesh-node"
    node_dir.mkdir()
    relay.generate_self_signed_cert(
        node_dir / "relay-cert.pem", node_dir / "relay-key.pem", "web-1", days=1
    )
    NodeRelayStore(tmp_path).set("web-1", NODE_ENTRY)
    doctor(tmp_path)
    output = capsys.readouterr().out
    assert "Node certificate" in output
    assert "WARN" in output
    assert "1 day" in output


def test_readme_documents_the_relay_workflow():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Nodes behind NAT" in text
    assert "cm relay init" in text
    assert "cm node relay enable" in text
    assert "cm node relay import" in text
    assert "cm relay serve" in text
