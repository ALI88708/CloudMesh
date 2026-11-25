"""Regression tests for the full-repository audit (pass 03)."""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
from pathlib import Path

import pytest

import cloudmesh.main as cloudmesh_main
from cloudmesh.core import acl, features, plugins
from cloudmesh.core.advanced import NotifyManager, benchmark_disk, quick_ssh
from cloudmesh.core.alerts import AlertManager
from cloudmesh.core.checkpoint import CheckpointManager
from cloudmesh.core.gpu import GPUTelemetry
from cloudmesh.core.groups import GroupsManager
from cloudmesh.core.history import HistoryManager
from cloudmesh.core.jobs import JobManager
from cloudmesh.core.monitor import ResourceMonitor
from cloudmesh.core.osprofile import LinuxProfile
from cloudmesh.core.security import SecurityManager
from cloudmesh.core.shamir import ShamirSecretSharing
from cloudmesh.core.storage import StorageManager
from cloudmesh.core.transfer import FileTransfer
from cloudmesh.core.weather import WeatherForecast


def test_search_files_quotes_arguments_and_handles_empty_output():
    seen = []

    class FakeMgr:
        def execute(self, name, cmd):
            seen.append(cmd)
            return {"stdout": "\n", "stderr": "", "exit_code": 0}

    out = features.search_files(FakeMgr(), "web1", "-bad; whoami", "*'; id #")
    assert out == []
    assert "'./-bad; whoami'" in seen[0]
    assert "\"*'; id #\"" in seen[0] or "'*'\"'\"'; id #'" in seen[0]


def test_network_speed_test_rejects_unsafe_targets():
    called = []

    class FakeMgr:
        def execute(self, name, cmd):
            called.append(cmd)
            return {"stdout": "rtt min/avg/max = 1/2/3 ms", "exit_code": 0}

    assert features.network_speed_test(FakeMgr(), "web1", target="-f 8.8.8.8") == "N/A"
    assert features.network_speed_test(FakeMgr(), "web1", target="8.8.8.8; id") == "N/A"
    assert called == []
    assert "avg" in features.network_speed_test(FakeMgr(), "web1", target="8.8.8.8", count=2)
    assert len(called) == 1


def test_decrypt_file_preserves_encrypted_parent_dir_and_export_sets_0600(tmp_path):
    nested = tmp_path / "dir.encrypted"
    nested.mkdir()
    plain = nested / "secret.txt"
    plain.write_text("top-secret", encoding="utf-8")

    key, enc_path = features.encrypt_file(str(plain))
    plain.unlink()
    restored = features.decrypt_file(enc_path, key)
    assert Path(restored) == nested / "secret.txt"
    assert Path(restored).read_text(encoding="utf-8") == "top-secret"

    # Non-.encrypted extension writes .decrypted instead of clobbering input
    alt = nested / "blob.bin"
    alt.write_bytes(Path(enc_path).read_bytes())
    alt_out = features.decrypt_file(str(alt), key)
    assert alt_out.endswith(".decrypted")
    assert Path(alt_out).read_text(encoding="utf-8") == "top-secret"

    sec = SecurityManager(tmp_path / "state")
    sec.save_config({"servers": {"s1": {"host": "10.0.0.1", "password": "pw"}}})
    exported = tmp_path / "exported.json"
    features.export_config(sec, str(exported))
    if os.name != "nt":
        assert stat.S_IMODE(exported.stat().st_mode) == 0o600


def test_notify_manager_private_permissions_and_discord_scheme_validation(tmp_path):
    notify_path = tmp_path / ".notify.json"
    mgr = NotifyManager(notify_file=notify_path)
    mgr.setup_telegram("bot-token", "12345")
    if os.name != "nt":
        assert stat.S_IMODE(notify_path.stat().st_mode) == 0o600

    with pytest.raises(ValueError, match="https:// or http://"):
        mgr.setup_discord("file:///etc/passwd")

    mgr._config["discord"] = {"webhook_url": "file:///etc/passwd"}
    assert mgr.send_discord("hello") is False


def test_quick_ssh_rejects_option_injection_and_benchmark_disk_runs(tmp_path):
    with pytest.raises(ValueError, match="Invalid SSH host"):
        quick_ssh("-oProxyCommand=id", user="root")
    with pytest.raises(ValueError, match="Invalid SSH user"):
        quick_ssh("10.0.0.5", user="-oProxyCommand=id")
    assert quick_ssh("10.0.0.5", user="deploy", port=2222) == "ssh -p 2222 deploy@10.0.0.5"

    bench = benchmark_disk(path=str(tmp_path), size_mb=1)
    assert bench["write_mb_s"] > 0
    assert bench["read_mb_s"] > 0


def test_alert_manager_fires_on_gpu_utilization_percent_and_pipe_rule_names(tmp_path):
    class FakeMonitor:
        def get_all_metrics(self, name):
            return {
                "cpu_percent": 10.0,
                "ram": {"percent": 20.0},
                "disk": {"percent": 30.0},
                "load": (4.5, 2.0, 1.0),
                "gpu": {"name": "RTX 4090", "utilization_percent": 95.0},
            }

    sent = []

    class FakeNotifier:
        def notify(self, msg):
            sent.append(msg)
            return {"telegram": True}

    mgr = AlertManager(FakeMonitor(), base_dir=tmp_path, notifier=FakeNotifier())
    mgr.add_rule("gpu|hot", "gpu", 80.0, server="gpu1", cooldown=300)
    mgr.add_rule("load-high", "load", 3.0, server="gpu1", cooldown=300)

    triggered = mgr.check_alerts()
    names = {a["rule"] for a in triggered}
    assert names == {"gpu|hot", "load-high"}
    assert len(sent) == 2

    # Second immediate check respects cooldown even with '|' in rule_name
    sent.clear()
    mgr.check_alerts()
    assert sent == []


def test_gpu_telemetry_parses_multi_gpu_output(monkeypatch):
    multi_line = (
        "NVIDIA A100, 72, 20480, 40960, 61\n"
        "NVIDIA A100, 15, 4096, 40960, 48\n"
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=multi_line, stderr=""),
    )
    gpu = GPUTelemetry().get_local_gpu()
    assert gpu is not None
    assert gpu["utilization_percent"] == 72.0
    assert gpu["temperature_c"] == 61.0

    class FakeMgr:
        def execute(self, name, cmd):
            return {"stdout": multi_line, "stderr": "", "exit_code": 0}

    remote_gpu = GPUTelemetry().get_remote_gpu(FakeMgr(), "gpu-host")
    assert remote_gpu is not None
    assert remote_gpu["utilization_percent"] == 72.0


def test_linux_profile_top_and_disk_detail_parsers():
    prof = LinuxProfile()
    top_cmd = prof.top_cmd("cpu", 5)
    assert "pid,%cpu,comm" in top_cmd
    parsed_top = prof.parse_top("  123 45.2 python3\n  456  3.1 sshd\n", "cpu", 5)
    assert parsed_top == [
        {"pid": "123", "usage": "45.2", "name": "python3"},
        {"pid": "456", "usage": "3.1", "name": "sshd"},
    ]

    # Single-partition Linux host where grep '^/' already stripped the header:
    raw_df = "/dev/vda1        50G   20G   30G  40% /\n"
    disks = prof.parse_disk_detail(raw_df)
    assert len(disks) == 1
    assert disks[0]["device"] == "/dev/vda1"
    assert disks[0]["mount"] == "/"

    # Headered df output also works without including the header row:
    headered_df = "Filesystem Size Used Avail Use% Mounted on\n" + raw_df
    assert prof.parse_disk_detail(headered_df) == disks


def test_monitor_calculate_weight_treats_zero_cpu_as_idle_not_saturated():
    mon = ResourceMonitor(server_manager=None)
    idle_weight = mon.calculate_weight(
        {"cpu_percent": 0.0, "ram": {"free_gb": 16.0}, "disk": {"free_gb": 50.0}}
    )
    busy_weight = mon.calculate_weight(
        {"cpu_percent": 100.0, "ram": {"free_gb": 16.0}, "disk": {"free_gb": 50.0}}
    )
    assert idle_weight > busy_weight
    assert idle_weight == 64.6
    assert busy_weight == 14.6


def test_weather_forecast_persists_across_reloads(tmp_path):
    wf_file = tmp_path / ".resource_weather.json"
    wf1 = WeatherForecast(data_file=wf_file)
    wf1.learn("web1", 25.0, 40.0)
    current_hour = int(next(iter(wf1._data["web1"].keys())))

    # Reload from disk in a fresh instance (JSON keys are strings on disk)
    wf2 = WeatherForecast(data_file=wf_file)
    pred = wf2.predict("web1", target_hour=current_hour)
    assert pred["status"] == "predicted"
    assert pred["cpu_ema"] == 25.0
    assert pred["ram_ema"] == 40.0
    profile = wf2.get_hourly_profile("web1")
    assert profile[current_hour]["samples"] == 1


def test_shamir_combine_rejects_mismatched_share_lengths_and_invalid_ids():
    shares = ShamirSecretSharing.split(b"0123456789abcdef", 3, 2)
    short_shares = ShamirSecretSharing.split(b"short", 3, 2)

    with pytest.raises(ValueError, match="Invalid share data"):
        ShamirSecretSharing.combine([shares[0], (shares[1][0], short_shares[1][1])])

    with pytest.raises(ValueError, match="Invalid share ID"):
        ShamirSecretSharing.combine([(0, shares[0][1]), shares[1]])


def test_transfer_between_uses_secure_temp_and_upload_dir_waits_for_mkdir(tmp_path):
    events = []

    class FakeChannel:
        def recv_exit_status(self):
            events.append("mkdir_done")
            return 0

    class FakeStdout:
        channel = FakeChannel()

    class FakeSFTP:
        def get(self, remote_path, local_path):
            Path(local_path).write_text("payload", encoding="utf-8")

        def put(self, local_path, remote_path):
            events.append(("put", remote_path, Path(local_path).name))

        def close(self):
            pass

    class FakeSSH:
        def open_sftp(self):
            return FakeSFTP()

        def exec_command(self, cmd):
            events.append(("exec", cmd))
            return None, FakeStdout(), None

    class FakeServerMgr:
        def connect(self, name):
            return FakeSSH()

    ft = FileTransfer(FakeServerMgr())
    res = ft.transfer_between("src", "dst", "/var/log/app.log", "/backup/app.log")
    assert res["success"] is True
    put_events = [e for e in events if isinstance(e, tuple) and e[0] == "put"]
    assert put_events[0][2].startswith("cloudmesh_transfer_")

    events.clear()
    src_dir = tmp_path / "upload_src"
    (src_dir / "sub").mkdir(parents=True)
    (src_dir / "sub" / "a.txt").write_text("hello", encoding="utf-8")
    ft.upload_directory("dst", str(src_dir), "/opt/app")
    assert events[0][0] == "exec"
    assert events[1] == "mkdir_done"
    assert events[2][0] == "put"


def test_path_traversal_guards_and_node_job_checkpoint_recover(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))

    cp = CheckpointManager(tmp_path / ".checkpoints")
    jm = JobManager(tmp_path / ".jobs")
    hm = HistoryManager(resource_monitor=None, base_dir=tmp_path)

    for bad in ("../escape", "a/b", r"a\b", ""):
        with pytest.raises(ValueError):
            cp.save_checkpoint(bad, "echo 1", "node1", 50)
        with pytest.raises(ValueError):
            jm.get_job(bad)
        with pytest.raises(ValueError):
            hm.get_history(bad)

    # End-to-end node job checkpoint + recover when all nodes are offline
    monkeypatch.setattr(cloudmesh_main, "_load_node_keys", lambda: {
        "node1": {"host": "10.0.0.9", "port": 9999, "key": "k" * 64},
    })

    class FakeNodeClient:
        def ping(self):
            return False

        def check_job(self, job_id):
            return {
                "status": "running",
                "command": "python train.py",
                "stdout": "step 10",
                "stderr": "",
                "exit_code": None,
            }

    monkeypatch.setattr(
        cloudmesh_main.NodeClient,
        "from_config",
        classmethod(lambda cls, info, name=None: FakeNodeClient()),
    )

    cloudmesh_main.cmd_job_checkpoint(
        argparse.Namespace(name="node1", job_id="job12345")
    )
    saved = CheckpointManager().load_checkpoint("job12345")
    assert saved is not None
    assert saved["command"] == "python train.py"

    # Even with 0 online nodes (alive_nodes == set()), needs_recovery finds job12345
    assert len(CheckpointManager().needs_recovery(set())) == 1
    cloudmesh_main.cmd_job_recover(argparse.Namespace(relaunch=True, target="node2"))
    assert CheckpointManager().load_checkpoint("job12345") is None
    assert len(JobManager().list_jobs()) == 1


def test_groups_empty_sqlite_and_private_acl_plugins_and_config_relay(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    sec = SecurityManager(tmp_path)
    st = StorageManager(tmp_path)
    gm = GroupsManager(sec, st)
    gm.create_group("web")
    gm.add_to_group("web", "srv1")
    # Simulate external deletion in SQLite while gm.config still had 'web'
    st.delete_group("web")
    assert gm.list_groups() == {}
    assert gm.get_group_devices("web") == []

    acl.add_user("alice", "StrongPass!123", "admin")
    plugins.add_plugin("check", "uptime")
    if os.name != "nt":
        assert stat.S_IMODE((tmp_path / "data" / "acl.json").stat().st_mode) == 0o600
        assert stat.S_IMODE((tmp_path / "data" / "plugins.json").stat().st_mode) == 0o600

    (tmp_path / ".node_relay.json").write_text('{"n1": {"url": "1.2.3.4:9997"}}', encoding="utf-8")
    out_dir = tmp_path / "exported_cfg"
    cloudmesh_main.cmd_config(argparse.Namespace(action="export", output=str(out_dir)))
    assert (out_dir / ".node_relay.json").is_file()

    site_html = (Path(__file__).resolve().parents[2] / "site" / "index.html").read_text(encoding="utf-8")
    assert "<strong>301</strong> command paths" in site_html
