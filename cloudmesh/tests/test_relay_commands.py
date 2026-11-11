from argparse import Namespace

import cloudmesh.main as main_module
from cloudmesh.core.node_relay import RelayProfileStore


class FakeNodeStore:
    last_error = None

    def get(self, name):
        if name != "web-1":
            return None
        return {"relay_id": "ab" * 16, "url": "relay.test:9997"}


def test_relay_init_writes_a_profile_and_prints_commands(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    args = Namespace(
        url="relay.example.com:9997",
        config=str(tmp_path / "relay.json"),
        bind="0.0.0.0",
        port=9997,
        tls_cert=None,
        tls_key=None,
        force=False,
    )
    main_module.cmd_relay_init(args)
    output = capsys.readouterr().out
    assert "cm relay add" in output
    assert (tmp_path / "relay.json").is_file()


def test_relay_add_stores_the_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    main_module.cmd_relay_add(
        Namespace(
            url="relay.test:9997",
            key="ab" * 32,
            fingerprint="cd" * 32,
            ca_file=None,
        )
    )
    assert RelayProfileStore(tmp_path).get("relay.test:9997")["admin_key"] == "ab" * 32


def test_relay_status_uses_the_admin_client(monkeypatch, capsys):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def status(self):
            return {"type": "status", "data": {"totals": {"parked": 2}}}

    monkeypatch.setattr(main_module, "RelayAdminClient", FakeClient)
    main_module.cmd_relay_status(Namespace(relay="relay.test:9997"))
    assert "parked" in capsys.readouterr().out


def test_relay_revoke_uses_the_node_sidecar(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def revoke(self, relay_id):
            calls.append(relay_id)
            return {"data": {"success": True}}

    monkeypatch.setattr(main_module, "RelayAdminClient", FakeClient)
    monkeypatch.setattr(main_module, "NodeRelayStore", lambda: FakeNodeStore())
    main_module.cmd_relay_revoke(Namespace(name="web-1", relay="relay.test:9997"))
    assert calls == ["ab" * 16]


def test_relay_parser_wires_every_subcommand():
    parser = main_module.build_parser()
    for argv in (
        ["relay", "init"],
        ["relay", "add", "--url", "h:1", "--key", "k"],
        ["relay", "serve"],
        ["relay", "status"],
        ["relay", "revoke", "-n", "n"],
    ):
        assert parser.parse_args(argv).action
