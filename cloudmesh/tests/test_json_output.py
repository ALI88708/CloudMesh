import argparse
import json

from cloudmesh.main import cmd_disk, cmd_monitor, cmd_ping


class _Servers:
    def __init__(self, names):
        self.names = names

    def list_servers(self):
        return self.names


class _Monitor:
    def __init__(self, samples):
        self.samples = samples

    def get_all_metrics(self, name):
        sample = self.samples[name]
        if isinstance(sample, Exception):
            raise sample
        return sample

    def get_local_metrics(self):
        return self.samples["local"]


def _wire(monkeypatch, monitor, servers=()):
    import cloudmesh.main as main_module

    monkeypatch.setattr(
        main_module,
        "init_components",
        lambda: (None, _Servers(list(servers)), monitor),
    )
    return main_module


def _sample(cpu=5.0, ram=20.0, disk=30.0):
    return {
        "cpu_percent": cpu,
        "ram": {"total_gb": 16.0, "used_gb": 3.2, "percent": ram},
        "disk": {"total_gb": 100.0, "used_gb": 30.0, "percent": disk},
    }


def _payload(capsys):
    out = capsys.readouterr().out
    return out, json.loads(out)


def test_monitor_json_emits_one_entry_per_server(monkeypatch, capsys):
    _wire(monkeypatch, _Monitor({"web-1": _sample(cpu=12.5)}), servers=["web-1"])

    cmd_monitor(argparse.Namespace(name=None, local=False, as_json=True))

    raw, data = _payload(capsys)
    assert data["web-1"]["cpu_percent"] == 12.5
    assert data["web-1"]["ram"]["percent"] == 20.0
    assert "\u2500" not in raw


def test_monitor_json_reports_an_unreachable_server_without_failing(monkeypatch, capsys):
    _wire(
        monkeypatch,
        _Monitor({"web-1": _sample(), "web-2": OSError("connection refused")}),
        servers=["web-1", "web-2"],
    )

    cmd_monitor(argparse.Namespace(name=None, local=False, as_json=True))

    _, data = _payload(capsys)
    assert data["web-1"]["cpu_percent"] == 5.0
    assert "connection refused" in data["web-2"]["error"]


def test_monitor_json_supports_the_local_machine(monkeypatch, capsys):
    _wire(monkeypatch, _Monitor({"local": _sample(cpu=42.0)}))

    cmd_monitor(argparse.Namespace(name=None, local=True, as_json=True))

    _, data = _payload(capsys)
    assert data["local"]["cpu_percent"] == 42.0


def test_disk_json_emits_the_mounts(monkeypatch, capsys):
    main_module = _wire(monkeypatch, _Monitor({}), servers=["web-1"])
    mounts = [
        {"device": "/dev/sda1", "size": "100G", "used": "30G",
         "avail": "70G", "use%": "30%", "mount": "/"},
    ]
    monkeypatch.setattr(main_module, "get_disk_detail", lambda _m, _n: mounts)

    cmd_disk(argparse.Namespace(name=None, as_json=True))

    _, data = _payload(capsys)
    assert data["web-1"][0]["mount"] == "/"
    assert data["web-1"][0]["use%"] == "30%"


def test_ping_json_emits_the_probe_results(monkeypatch, capsys):
    main_module = _wire(monkeypatch, _Monitor({}), servers=["web-1"])
    monkeypatch.setattr(main_module, "_load_node_keys", lambda: {})
    monkeypatch.setattr(
        main_module,
        "ping_all",
        lambda _m, _k: {
            "web-1": {"type": "server", "online": False, "msg": "timeout"},
        },
    )

    cmd_ping(argparse.Namespace(no_nodes=False, as_json=True))

    _, data = _payload(capsys)
    assert data["web-1"]["online"] is False
    assert data["web-1"]["msg"] == "timeout"
