from argparse import Namespace

import pytest

import cloudmesh.main as main_module
from cloudmesh.core.node_relay import NodeRelayStore, RelayError

RELAY_URL = "relay.test:9997"
ENTRY = {
    "relay_id": "ab" * 16,
    "url": RELAY_URL,
    "relay_fingerprint": "cd" * 32,
    "node_fingerprint": "ef" * 32,
}
DIRECT_NODE = {"host": "10.0.0.5", "port": 9999, "key": "k" * 64}
RELAY_NODE = {"host": "relay.test", "port": 9997, "key": "k" * 64}


class FakeClient:
    last_error = None

    def ping(self):
        return True

    def get_info(self):
        return {}

    def get_metrics(self):
        return {}


def test_node_relay_enable_requires_ssh_or_local():
    args = Namespace(
        name="web-1",
        relay=RELAY_URL,
        ssh_host=None,
        ssh_user=None,
        ssh_key=None,
        ssh_port=22,
        local=False,
        pool=4,
        cert=None,
        key=None,
    )
    with pytest.raises(SystemExit) as exc:
        main_module.cmd_node_relay(args)
    assert exc.value.code == 2


def test_node_relay_import_writes_the_sidecar(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    args = Namespace(
        relay_action="import",
        name="web-1",
        relay=RELAY_URL,
        relay_id="ab" * 16,
        token="cd" * 32,
        node_fingerprint="ef" * 32,
        relay_fingerprint="11" * 32,
    )
    main_module.cmd_node_relay(args)
    assert NodeRelayStore(tmp_path).get("web-1")["relay_id"] == "ab" * 16


def test_node_add_with_relay_rolls_back_on_enable_failure(monkeypatch):
    keys = {}
    monkeypatch.setattr(main_module, "_load_node_keys", lambda: dict(keys))

    def save(value):
        keys.clear()
        keys.update(value)

    monkeypatch.setattr(main_module, "_save_node_keys", save)

    class FailingProvisioner:
        def __init__(self, *a, **k):
            pass

        def enable_ssh(self, *a, **k):
            raise RelayError("enroll failed")

    monkeypatch.setattr(main_module, "RelayProvisioner", FailingProvisioner)
    args = Namespace(
        name="web-1",
        host=None,
        port=9999,
        auth_key="k" * 64,
        tls=False,
        ca_file=None,
        relay=RELAY_URL,
        ssh_host="10.0.0.5",
        ssh_user="root",
        ssh_key=None,
        ssh_port=22,
        pool=4,
    )
    with pytest.raises(SystemExit) as exc:
        main_module.cmd_node_add_cloud(args)
    assert exc.value.code == 1
    assert "web-1" not in keys


def test_node_list_shows_relay_transport(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    NodeRelayStore(tmp_path).set("web-1", ENTRY)
    keys = {"web-1": RELAY_NODE, "web-2": DIRECT_NODE}
    monkeypatch.setattr(main_module, "_load_node_keys", lambda: keys)
    monkeypatch.setattr(
        main_module.NodeClient,
        "from_config",
        classmethod(lambda cls, info, name=None: FakeClient()),
    )
    main_module.cmd_node_list_cloud(Namespace())
    output = capsys.readouterr().out
    assert "RELAY" in output
    assert "DIRECT" in output


def test_node_commands_pass_the_node_name(monkeypatch):
    seen = []
    monkeypatch.setattr(main_module, "_load_node_keys", lambda: {"web-1": DIRECT_NODE})
    monkeypatch.setattr(
        main_module.NodeClient,
        "from_config",
        classmethod(
            lambda cls, info, name=None: seen.append(name) or FakeClient()
        ),
    )
    main_module.cmd_node_test(Namespace(name="web-1"))
    assert seen == ["web-1"]


def test_node_relay_disable_revokes_and_removes_the_sidecar(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    NodeRelayStore(tmp_path).set("web-1", ENTRY)
    calls = []

    class FakeProvisioner:
        def __init__(self, *a, **k):
            pass

        def disable_ssh(self, name, url, **kwargs):
            calls.append((name, url, kwargs.get("ssh_host")))
            NodeRelayStore(tmp_path).remove(name)
            return {
                "restart_ok": True,
                "restart_command": "systemctl restart cloudmesh-node",
            }

    monkeypatch.setattr(main_module, "RelayProvisioner", FakeProvisioner)
    args = Namespace(
        relay_action="disable",
        name="web-1",
        relay=RELAY_URL,
        ssh_host="10.0.0.5",
        ssh_user="root",
        ssh_key=None,
        ssh_port=22,
        local=False,
    )
    main_module.cmd_node_relay(args)
    assert calls == [("web-1", RELAY_URL, "10.0.0.5")]
    assert NodeRelayStore(tmp_path).get("web-1") is None


def test_node_relay_status_prints_the_relay_block(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    NodeRelayStore(tmp_path).set("web-1", ENTRY)
    main_module.cmd_node_relay(Namespace(relay_action="status", name="web-1"))
    output = capsys.readouterr().out
    assert RELAY_URL in output
    assert "ef" * 32 in output
