"""Regression tests for the second repository-wide bug-hunt pass.

Covers packaging of node installers, remote node staging, Windows/Linux
installer state preservation, standalone node agent imports and CLI validation,
replay-window NaN/bool/type hardening, long-lived relay sessions, full panic
key rotation with SQLite storage, `cm status`, `docker compose` / `firewall
add-rule` parser collisions, firewall shell-injection guards, script deploy
containment, multi-server process watchers, webhook/tunnel error handling,
`doctor --fix` under `CLOUDMESH_DIR`, and dynamic `CLOUDMESH_DIR` resolution.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
for _candidate in (str(REPO_ROOT), str(ROOT), str(ROOT / "node")):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

import cloudmesh_node
import cloudmesh_relay

import cloudmesh.main as cloudmesh_main
from cloudmesh.core import (
    database,
    docker,
    firewall,
    plugins,
    tunnels,
    watcher,
    webhooks,
)
from cloudmesh.core.deploy import PackageDeployer
from cloudmesh.core.nodekeyring import NodeKeyring
from cloudmesh.core.panic import PanicManager
from cloudmesh.core.storage import StorageManager


def test_pyproject_ships_node_installer_scripts():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = data["tool"]["setuptools"]["package-data"]["cloudmesh"]
    assert "node/*.sh" in patterns
    assert "node/*.bat" in patterns


def test_node_installer_stages_agent_and_relay_with_source_dir(monkeypatch, tmp_path):
    commands = []
    uploads = []

    class FakeServerManager:
        def execute(self, _name, command):
            commands.append(command)
            if command.startswith("mktemp -d "):
                return {
                    "stdout": "/tmp/cloudmesh-stage.xyz789\n",
                    "stderr": "",
                    "exit_code": 0,
                }
            if command.startswith("mktemp "):
                return {
                    "stdout": "/tmp/cloudmesh-install.abc123\n",
                    "stderr": "",
                    "exit_code": 0,
                }
            return {"stdout": "installed", "stderr": "", "exit_code": 0}

    class FakeTransfer:
        def __init__(self, _manager):
            pass

        def upload(self, _name, local, remote):
            uploads.append((Path(local).name, remote))
            assert Path(local).is_file()

    monkeypatch.setattr(cloudmesh_main, "FileTransfer", FakeTransfer)
    agent_file = tmp_path / "cloudmesh_node.py"
    relay_file = tmp_path / "cloudmesh_relay.py"
    agent_file.write_text("# agent\n", encoding="utf-8")
    relay_file.write_text("# relay\n", encoding="utf-8")

    res = cloudmesh_main._run_node_installer(
        FakeServerManager(),
        "srv",
        "#!/bin/sh\necho ok\n",
        extra_files={
            "cloudmesh_node.py": agent_file,
            "cloudmesh_relay.py": relay_file,
        },
    )

    assert res["exit_code"] == 0
    remote_targets = [remote for _, remote in uploads]
    assert "/tmp/cloudmesh-install.abc123" in remote_targets
    assert "/tmp/cloudmesh-stage.xyz789/cloudmesh_node.py" in remote_targets
    assert "/tmp/cloudmesh-stage.xyz789/cloudmesh_relay.py" in remote_targets
    assert any(
        cmd == "sh /tmp/cloudmesh-install.abc123 --source-dir /tmp/cloudmesh-stage.xyz789"
        for cmd in commands
    )
    assert any(cmd == "rm -rf /tmp/cloudmesh-stage.xyz789" for cmd in commands)
    assert any(cmd == "rm -f /tmp/cloudmesh-install.abc123" for cmd in commands)


def test_installers_fix_windows_arg_parse_and_preserve_sqlite_and_relay():
    win_bat = (REPO_ROOT / "cm_for-windows.bat").read_text(encoding="utf-8")
    node_bat = (ROOT / "node" / "node-install.bat").read_text(encoding="utf-8")
    linux_sh = (REPO_ROOT / "cm_for-linux.sh").read_text(encoding="utf-8")
    node_sh = (ROOT / "node" / "node-install.sh").read_text(encoding="utf-8")

    assert 'echo /S=DIR "%~1"' not in win_bat
    assert 'if /I "%~1"=="/S"' in win_bat
    assert "cloudmesh.db" in win_bat and ".secret.key" in win_bat
    assert "cloudmesh_relay.py" in win_bat

    assert r'mkdir "%INSTALL_DIR%\data"' in node_bat
    assert "cloudmesh_relay.py" in node_bat
    assert "exit /b 0\n\n:set_path" in node_bat.replace("\r\n", "\n")

    assert "cloudmesh_relay.py" in linux_sh
    assert "cloudmesh.db" in linux_sh
    assert r"while [ \$# -gt 0 ]; do" in linux_sh
    assert "--source-dir" in node_sh


def test_standalone_node_agent_imports_without_relay_module(tmp_path):
    isolated = tmp_path / "standalone"
    isolated.mkdir()
    shutil.copy2(ROOT / "node" / "cloudmesh_node.py", isolated / "cloudmesh_node.py")

    proc = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                f"import sys; sys.path.insert(0, {str(isolated)!r}); "
                "import cloudmesh_node; "
                "assert cloudmesh_node.cloudmesh_relay is None"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr


def test_node_cli_rejects_unknown_flags_on_non_relay_commands():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "node" / "cloudmesh_node.py"), "status", "--bogus-flag"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode == 2
    assert "unrecognized arguments: --bogus-flag" in proc.stderr


@pytest.mark.parametrize(
    "bad_ts",
    [float("nan"), float("inf"), float("-inf"), True, False, "12345"],
)
def test_replay_guards_reject_non_finite_and_boolean_timestamps(tmp_path, bad_ts):
    agent = cloudmesh_node.NodeAgent(
        port=0, auth_key="k" * 32, bind_host="127.0.0.1"
    )
    err = agent._check_request_replay({"nonce": "abcd1234", "timestamp": bad_ts})
    assert err is not None

    cache = cloudmesh_relay.NonceCache()
    ok, _ = cache.accept("scope", "aa" * 16, bad_ts, now=1.0)
    assert ok is False

    listener = cloudmesh_node.SpacListener(
        "k" * 32, 9998, 9999, 5, lambda *_: None
    )
    if not (isinstance(bad_ts, float) and (math.isnan(bad_ts) or math.isinf(bad_ts))):
        msg = f"{bad_ts}:nonce1"
        sig = hmac.new(b"k" * 32, msg.encode(), hashlib.sha256).hexdigest()
        pkt = json.dumps({"timestamp": bad_ts, "nonce": "nonce1", "hmac": sig}).encode()
        assert listener._validate_packet(pkt, "127.0.0.1") is False


@pytest.mark.parametrize("bad_nonce", [["list"], {"dict": 1}, 12345, True])
def test_replay_guards_reject_unhashable_or_non_string_nonces(bad_nonce):
    agent = cloudmesh_node.NodeAgent(
        port=0, auth_key="k" * 32, bind_host="127.0.0.1"
    )
    err = agent._check_request_replay({"nonce": bad_nonce, "timestamp": time.time()})
    assert err == "Malformed replay protection fields"

    listener = cloudmesh_node.SpacListener(
        "k" * 32, 9998, 9999, 5, lambda *_: None
    )
    pkt = json.dumps(
        {"timestamp": time.time(), "nonce": bad_nonce, "hmac": "deadbeef"}
    ).encode()
    assert listener._validate_packet(pkt, "127.0.0.1") is False


@pytest.mark.timeout(20)
def test_relay_pump_pair_does_not_abort_commands_longer_than_four_seconds(tmp_path):
    cfg_path = tmp_path / "relay.json"
    cloudmesh_relay.init_relay(cfg_path, bind="127.0.0.1", port=0)
    server = cloudmesh_relay.RelayServer(cloudmesh_relay.RelayConfig.load(cfg_path))

    node_a, node_b = socket.socketpair()
    ctrl_a, ctrl_b = socket.socketpair()
    pump_thread = threading.Thread(
        target=server._pump_pair, args=(node_b, ctrl_b), daemon=True
    )
    pump_thread.start()

    try:
        ctrl_a.sendall(b"ping-before-long-work")
        assert node_a.recv(64) == b"ping-before-long-work"
        # Previously _pump_pair joined each pump thread for 2.0s (4.0s total)
        # and then forcibly shut down both sockets.
        time.sleep(4.4)
        node_a.sendall(b"delayed-response-ok")
        assert ctrl_a.recv(64) == b"delayed-response-ok"
    finally:
        node_a.close()
        ctrl_a.close()
        pump_thread.join(5.0)


def test_execute_panic_rotates_and_reencrypts_sqlite_stored_nodes(
    tmp_path, monkeypatch
):
    storage = StorageManager(tmp_path)
    keyring = NodeKeyring(storage=storage, base_dir=tmp_path)
    keyring.save(
        {
            "online-node": {"host": "10.0.0.1", "port": 9999, "key": "old-online"},
            "offline-node": {"host": "10.0.0.2", "port": 9999, "key": "old-offline"},
        }
    )

    seen_old_keys = {}

    class FakeClient:
        def __init__(self, host, auth_key):
            self.host = host
            self.auth_key = auth_key

        @classmethod
        def from_config(cls, node, name=None, base_dir=None):
            seen_old_keys[name] = node.get("key")
            return cls(node["host"], node.get("key"))

        def rotate_key(self, new_key):
            if self.host == "10.0.0.1" and self.auth_key == "old-online":
                return {"success": True}
            return {"success": False, "message": "offline"}

    monkeypatch.setattr("cloudmesh.core.node_client.NodeClient", FakeClient)

    manager = PanicManager(base_dir=tmp_path)
    actions = manager.execute_panic()

    assert seen_old_keys == {
        "online-node": "old-online",
        "offline-node": "old-offline",
    }
    assert any("Rotated 'online-node'" in a for a in actions)

    # Fresh StorageManager + NodeKeyring using the NEW .secret.key must decrypt!
    fresh_keyring = NodeKeyring(base_dir=tmp_path)
    reloaded = fresh_keyring.load()
    assert reloaded["online-node"]["key"] not in ("", None, "old-online")
    assert len(reloaded["online-node"]["key"]) == 64
    assert reloaded["offline-node"]["key"] == "old-offline"

    pending = json.loads((tmp_path / ".panic_pending.json").read_text(encoding="utf-8"))
    assert pending["offline-node"]["old_key"] == "old-offline"


def test_cmd_status_reports_online_node_metrics(monkeypatch, capsys):
    class FakeClient:
        def ping(self):
            return True

        def get_metrics(self):
            return {
                "cpu_percent": 25.0,
                "ram": {"percent": 40.0},
                "disk": {"percent": 55.0},
            }

    monkeypatch.setattr(
        cloudmesh_main,
        "_load_node_keys",
        lambda: {"web-1": {"host": "10.0.0.5", "port": 9999, "key": "secret"}},
    )
    monkeypatch.setattr(
        cloudmesh_main.NodeClient,
        "from_config",
        classmethod(lambda cls, info, name=None: FakeClient()),
    )

    cloudmesh_main.cmd_status(argparse.Namespace(as_json=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["web-1"]["status"] == "online"
    assert payload["web-1"]["cpu"] == 25.0
    assert payload["web-1"]["ram"] == 40.0
    assert payload["web-1"]["disk"] == 55.0


def test_docker_compose_and_firewall_add_rule_do_not_collide_on_action(monkeypatch):
    parser = cloudmesh_main.build_parser()

    compose_args = parser.parse_args(
        ["docker", "compose", "/srv/app", "-s", "web1", "-a", "down"]
    )
    assert compose_args.action == "compose"
    assert compose_args.compose_action == "down"

    fw_args = parser.parse_args(
        ["firewall", "add-rule", "-p", "443", "--proto", "tcp", "-a", "deny", "-s", "web1"]
    )
    assert fw_args.action == "add-rule"
    assert fw_args.rule_action == "deny"

    fwadd_args = parser.parse_args(["fwadd", "-p", "443", "-a", "deny", "-s", "web1"])
    seen_fw = []
    monkeypatch.setattr(
        firewall.FirewallManager,
        "add_rule",
        lambda self, port, proto="tcp", action="allow", server=None: (
            seen_fw.append((port, proto, action, server)) or "Rule added"
        ),
    )
    cloudmesh_main._alias_firewall_add(fwadd_args)
    assert seen_fw == [(443, "tcp", "deny", "web1")]

    seen_ssh = []
    monkeypatch.setattr(
        docker,
        "_get_server",
        lambda _n: {"host": "h", "user": "root", "key": "", "os_type": "linux"},
    )
    monkeypatch.setattr(
        docker,
        "_run_ssh",
        lambda _h, _u, _k, cmd: (seen_ssh.append(cmd) or ("", 0)),
    )
    out = docker.DockerManager().docker_compose("/srv/my app", "web1", "down")
    assert out == "Compose stopped"
    assert seen_ssh and seen_ssh[0].startswith("cd '/srv/my app' &&")


def test_firewall_rejects_shell_metacharacters_and_invalid_ports(monkeypatch):
    executed = []
    monkeypatch.setattr(
        firewall,
        "_get_server",
        lambda _n: {"host": "h", "user": "root", "key": ""},
    )
    monkeypatch.setattr(firewall, "_detect_backend", lambda *_a: "ufw")
    monkeypatch.setattr(
        firewall,
        "_run_ssh",
        lambda *_a: (executed.append(_a) or ("", 0)),
    )

    res_add = firewall.firewall_add_rule("web1", "allow 80/tcp; touch /tmp/pwn")
    res_del = firewall.firewall_delete_rule("web1", "1 && touch /tmp/pwn")
    res_port = firewall.FirewallManager().check_port("80' && id && echo '", server="web1")

    assert res_add.startswith("Invalid rule")
    assert res_del.startswith("Invalid rule")
    assert res_port.startswith("Invalid port")
    assert executed == []


def test_deploy_run_script_sanitizes_script_name(monkeypatch):
    uploads = []
    commands = []

    class FakeServerManager:
        def get_server_info(self, _name):
            return {"os_type": "linux"}

        def execute(self, _name, cmd):
            commands.append(cmd)
            return {"exit_code": 0, "stdout": "done", "stderr": ""}

    class FakeTransfer:
        def __init__(self, _mgr):
            pass

        def upload(self, _srv, local, remote):
            uploads.append((local, remote))
            assert Path(local).is_file()

    monkeypatch.setattr("cloudmesh.core.transfer.FileTransfer", FakeTransfer)
    deployer = PackageDeployer(FakeServerManager())

    res = deployer.run_script("web1", "#!/bin/sh\necho hi\n", "../../etc/cron.d/evil.sh")
    assert res["success"] is True
    assert uploads[0][1] == "/tmp/evil.sh"
    assert not Path(uploads[0][0]).exists()

    with pytest.raises(ValueError):
        deployer.run_script("web1", "echo hi", "..")


def test_watcher_all_servers_does_not_false_trigger_when_running(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    monkeypatch.setattr(
        watcher,
        "_load_config",
        lambda: {
            "servers": {"s1": {"host": "h1"}, "s2": {"host": "h2"}},
            "nodes": {"node-only": {"host": "n1"}},
        },
    )
    monkeypatch.setattr(
        watcher,
        "check_process",
        lambda srv, proc: {"server": srv, "process": proc, "running": True, "instances": 1},
    )

    watcher.add_watcher("nginx-watch", "nginx", server=None, alert_on="stop")
    results = watcher.check_all_watchers()
    assert len(results) == 1
    assert results[0]["triggered"] is False
    assert watcher.watcher_alerts() == []


def test_database_check_all_marks_missing_server_unreachable(monkeypatch):
    monkeypatch.setattr(
        database,
        "_load_config",
        lambda: {"servers": {}, "nodes": {"ghost": {"host": "10.0.0.9"}}},
    )
    rows = database.db_check_all()
    assert rows == [
        {
            "server": "ghost",
            "status": "unreachable",
            "details": "Server 'ghost' not found",
        }
    ]


def test_webhooks_url_validation_and_named_test_delivery(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))

    bad = webhooks.add_webhook("evil", "file:///etc/passwd")
    assert bad.startswith("Invalid webhook URL")
    bad_flag = webhooks.add_webhook("flag", "-Khttp://example.com")
    assert bad_flag.startswith("Invalid webhook URL")

    ok = webhooks.add_webhook("ops", "https://hooks.example.com/notify")
    assert ok == "Webhook 'ops' added"

    calls = []
    monkeypatch.setattr(
        webhooks.subprocess,
        "run",
        lambda cmd, **kw: (calls.append(cmd) or SimpleNamespace(returncode=0, stderr="")),
    )
    res = webhooks.test_webhook("ops")
    assert res == [{"webhook": "ops", "status": "sent"}]
    assert len(calls) == 1
    assert "--" in calls[0]


def test_tunnel_start_reports_ssh_nonzero_exit(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    tunnels.add_tunnel("db", "10.0.0.1", "root", 15432, "127.0.0.1", 5432)
    monkeypatch.setattr(
        tunnels.subprocess,
        "run",
        lambda *_a, **_kw: SimpleNamespace(
            returncode=255, stdout="", stderr="Connection refused"
        ),
    )

    msg = tunnels.start_tunnel("db")
    assert msg.startswith("Failed to start tunnel:")
    assert tunnels.tunnel_status()["active"] == []


def test_doctor_repairs_and_dynamic_paths_follow_cloudmesh_dir(monkeypatch, tmp_path):
    source_base = tmp_path / "pkg"
    state_dir = tmp_path / "sandbox"
    source_base.mkdir()
    state_dir.mkdir()

    monkeypatch.setenv("CLOUDMESH_DIR", str(state_dir))
    assert cloudmesh_main._node_keys_file() == state_dir / ".node_keys.json"

    plugins.add_plugin("hello", "echo hi")
    assert (state_dir / "data" / "plugins.json").is_file()

    corrupt_keys = state_dir / ".node_keys.json"
    corrupt_keys.write_text("{corrupt", encoding="utf-8")
    secret = state_dir / ".secret.key"
    secret.write_bytes(b"k" * 44)
    if os.name != "nt":
        secret.chmod(0o644)

    actions = cloudmesh_main._doctor_repairs(source_base, state_dir)
    assert (state_dir / ".node_keys.json.bak").read_text(encoding="utf-8") == "{corrupt"
    assert json.loads(corrupt_keys.read_text(encoding="utf-8")) == {}
    if os.name != "nt":
        assert stat.S_IMODE(secret.stat().st_mode) == 0o600
    assert any(".bak" in a for a in actions)


def test_v5_migrate_and_server_manager_preserve_sqlite_only_invariant(tmp_path):
    from cloudmesh.core.migrate import MigrationManager
    from cloudmesh.core.security import SecurityManager
    from cloudmesh.core.server import ServerManager
    from cloudmesh.core.storage import StorageManager

    # Flow 1: docs/UPGRADING.md (`ServerManager` -> `cm migrate --verify` -> `cm doctor`)
    dir_a = tmp_path / "flow_a"
    dir_a.mkdir()
    sec_a = SecurityManager(base_dir=str(dir_a))
    store_a = StorageManager(dir_a)
    # Pre-seed one server so retry/idempotent import is also exercised
    store_a.add_server("bsd-1", "10.0.0.10", "admin")
    sec_a.save_config(
        {
            "servers": {
                "bsd-1": {
                    "host": "10.0.0.10",
                    "user": "admin",
                    "os_type": "freebsd",
                    "status": "connected",
                },
                "web-2": {
                    "host": "10.0.0.11",
                    "user": "root",
                    "os_type": "openbsd",
                },
            }
        }
    )

    mgr_a = ServerManager(sec_a, store_a)
    assert sorted(mgr_a.list_servers()) == ["bsd-1", "web-2"]
    assert mgr_a.get_server_info("bsd-1")["os_type"] == "freebsd"
    assert mgr_a.get_server_info("bsd-1")["status"] == "connected"
    assert mgr_a.get_server_info("web-2")["os_type"] == "openbsd"
    assert "servers" not in sec_a.load_config()

    verify_a = MigrationManager(dir_a).verify()
    assert verify_a["ok"] is True, verify_a
    ok_a, _ = cloudmesh_main._server_registry_check(sec_a, store_a)
    assert ok_a is True

    # Flow 2: running `cm migrate` directly on a 4.x config removes JSON servers
    dir_b = tmp_path / "flow_b"
    dir_b.mkdir()
    sec_b = SecurityManager(base_dir=str(dir_b))
    sec_b.save_config(
        {
            "servers": {
                "srv-1": {
                    "host": "10.0.0.20",
                    "user": "root",
                    "os_type": "netbsd",
                }
            },
            "settings": {"monitor_interval": 7},
        }
    )
    mig_b = MigrationManager(dir_b)
    mig_b.migrate_all(dry_run=False)
    assert mig_b.errors == []
    assert "servers" not in SecurityManager(base_dir=str(dir_b)).load_config()
    assert StorageManager(dir_b).get_server("srv-1")["os_type"] == "netbsd"
    assert MigrationManager(dir_b).verify()["ok"] is True


def test_v5_config_export_and_import_round_trip_on_fresh_install(
    monkeypatch, tmp_path, capsys
):
    from cloudmesh.core.security import SecurityManager
    from cloudmesh.core.server import ServerManager
    from cloudmesh.core.storage import StorageManager

    src_state = tmp_path / "src_state"
    dst_state = tmp_path / "dst_state"
    backup_dir = tmp_path / "exported"
    src_state.mkdir()
    dst_state.mkdir()

    monkeypatch.setenv("CLOUDMESH_DIR", str(src_state))
    sec_src = SecurityManager(base_dir=str(src_state))
    store_src = StorageManager(src_state)
    ServerManager(sec_src, store_src).add_server(
        "prod-1", "10.9.0.1", "ubuntu", password="s3cret-password"
    )
    (src_state / ".aliases.json").write_text(
        json.dumps({"st": "uptime"}), encoding="utf-8"
    )
    profiles_dir = src_state / ".profiles"
    profiles_dir.mkdir()
    (profiles_dir / "prod.json").write_text("{}", encoding="utf-8")

    cloudmesh_main.cmd_config(
        SimpleNamespace(action="export", output=str(backup_dir))
    )
    assert (backup_dir / "cloudmesh.db").is_file()
    assert (backup_dir / ".secret.key").is_file()

    # Import into a brand-new empty directory where target files do not exist yet
    monkeypatch.setenv("CLOUDMESH_DIR", str(dst_state))
    cloudmesh_main.cmd_config(
        SimpleNamespace(action="import", source=str(backup_dir))
    )

    restored_mgr = ServerManager(
        SecurityManager(base_dir=str(dst_state)), StorageManager(dst_state)
    )
    assert restored_mgr.list_servers() == ["prod-1"]
    assert restored_mgr.get_server_info("prod-1")["password"] == "s3cret-password"
    assert (dst_state / ".profiles" / "prod.json").is_file()
    if os.name != "nt":
        assert stat.S_IMODE((dst_state / ".secret.key").stat().st_mode) == 0o600

    capsys.readouterr()
    cloudmesh_main.cmd_config(SimpleNamespace(action="show", name="secret_key"))
    out_key = capsys.readouterr().out
    assert "redacted" in out_key.lower()
    cloudmesh_main.cmd_config(SimpleNamespace(action="show", name="database"))
    out_db = capsys.readouterr().out
    assert "binary/encrypted" in out_db.lower()


def test_v5_node_accepts_legacy_require_nonce_flag_from_v45_units(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cloudmesh_node, "cmd_start", lambda **kwargs: calls.append(kwargs)
    )
    monkeypatch.setattr(sys, "argv", ["cloudmesh_node.py", "start", "--require-nonce"])
    cloudmesh_node.main()
    assert calls[-1]["require_nonce"] is True

    monkeypatch.setattr(
        sys,
        "argv",
        ["cloudmesh_node.py", "start", "--require-nonce", "--allow-legacy"],
    )
    with pytest.raises(SystemExit) as exc:
        cloudmesh_node.main()
    assert exc.value.code == 2

