"""Regression tests for the 4.0.0 hardening audit.

Each test names the production behaviour it protects: profile secrecy, the
SQLite-to-legacy server lookup bridge, sandbox-aware storage, remote path
containment, bounded node responses, and shell quoting for user-supplied
values.
"""

from __future__ import annotations

import importlib
import json
import os
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cloudmesh.core.advanced import ProfileManager
from cloudmesh.core.node_client import NodeClient
from cloudmesh.core.security import SecurityManager
from cloudmesh.core.storage import StorageManager
from cloudmesh.core.sync import DirectorySync


def test_profile_save_encrypts_secrets_and_round_trips(tmp_path):
    security = SecurityManager(base_dir=tmp_path)
    manager = ProfileManager(profiles_dir=tmp_path / ".profiles", security=security)
    config = {"servers": {"prod": {"password": "hunter2"}}}

    manager.save_profile("production", config)

    raw = (tmp_path / ".profiles" / "production.json").read_bytes()
    assert b"hunter2" not in raw
    assert manager.load_profile("production") == config


def test_profile_names_cannot_escape_the_profiles_directory(tmp_path):
    manager = ProfileManager(
        profiles_dir=tmp_path / ".profiles",
        security=SecurityManager(base_dir=tmp_path),
    )

    with pytest.raises(ValueError):
        manager.save_profile("../escape", {"servers": {}})

    assert not (tmp_path / "escape.json").exists()


def test_profile_loader_still_reads_legacy_plaintext_files(tmp_path):
    manager = ProfileManager(
        profiles_dir=tmp_path / ".profiles",
        security=SecurityManager(base_dir=tmp_path),
    )
    config = {"servers": {"legacy": {"host": "old.example"}}}
    (tmp_path / ".profiles" / "legacy.json").write_text(json.dumps(config))

    assert manager.load_profile("legacy") == config


def test_profile_default_directory_follows_cloudmesh_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))

    manager = ProfileManager()

    assert manager.dir == tmp_path / ".profiles"


def test_state_managers_follow_cloudmesh_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    from cloudmesh.core.advanced import NotifyManager, ScheduleManager, TemplateManager
    from cloudmesh.core.checkpoint import CheckpointManager
    from cloudmesh.core.gossip import GossipManager
    from cloudmesh.core.weather import WeatherForecast

    assert ScheduleManager().file == tmp_path / ".schedule.json"
    assert NotifyManager().file == tmp_path / ".notify.json"
    assert TemplateManager().file == tmp_path / ".templates.json"
    assert CheckpointManager().checkpoint_dir == tmp_path / ".checkpoints"
    assert GossipManager().data_file == tmp_path / ".gossip_trust.json"
    assert WeatherForecast().data_file == tmp_path / ".resource_weather.json"


def test_feature_data_directory_follows_cloudmesh_dir(tmp_path):
    root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["CLOUDMESH_DIR"] = str(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import cloudmesh.core.webhooks as w; print(w.DATA_DIR)",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == tmp_path / "data"


@pytest.mark.parametrize(
    "module_name",
    ["database", "docker", "firewall", "logagg", "reshistory", "watcher"],
)
def test_legacy_modules_read_servers_from_the_current_store(
    monkeypatch, tmp_path, module_name
):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    storage = StorageManager(tmp_path)
    storage.add_server(
        "demo",
        "127.0.0.1",
        "root",
        key_path=str(tmp_path / "id_ed25519"),
    )

    module = importlib.import_module(f"cloudmesh.core.{module_name}")
    server = module._get_server("demo")

    assert server is not None
    assert server["host"] == "127.0.0.1"
    assert server["key"] == str(tmp_path / "id_ed25519")


@pytest.mark.parametrize(
    "module_name",
    ["database", "docker", "firewall", "logagg", "reshistory", "watcher"],
)
def test_legacy_modules_still_read_an_existing_json_config(
    monkeypatch, tmp_path, module_name
):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "cloudmesh.json").write_text(
        json.dumps(
            {
                "servers": {
                    "legacy": {
                        "host": "legacy.example",
                        "user": "root",
                        "key": "/keys/legacy",
                    }
                }
            }
        )
    )

    module = importlib.import_module(f"cloudmesh.core.{module_name}")

    assert module._get_server("legacy")["host"] == "legacy.example"


def test_node_client_key_file_follows_cloudmesh_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))

    client = NodeClient("127.0.0.1", 19999, auth_key="x" * 32)

    assert client._key_file == tmp_path / ".node_keys.json"


class _OversizedResponseSocket:
    def __init__(self, *args, **kwargs):
        self._sent_header = False

    def settimeout(self, *_args):
        return None

    def connect(self, *_args):
        return None

    def sendall(self, _data):
        return None

    def recv(self, _size):
        if not self._sent_header:
            self._sent_header = True
            return (60 * 1024 * 1024).to_bytes(4, "big")
        return b""

    def close(self):
        return None


def test_node_client_rejects_an_oversized_response(monkeypatch):
    monkeypatch.setattr(
        "cloudmesh.core.node_client.socket.socket",
        lambda *args, **kwargs: _OversizedResponseSocket(),
    )
    client = NodeClient("127.0.0.1", 19999, auth_key="x" * 32)

    response = client._send({"action": "ping", "auth": "x" * 32})

    assert "too large" in response["message"].lower()


class _EscapeServerManager:
    def __init__(self, remote_dir, remote_file):
        self.remote_dir = remote_dir
        self.remote_file = remote_file
        self.commands = []

    def get_server_info(self, _name):
        return {"os_type": "linux"}

    def execute(self, _name, command):
        self.commands.append(command)
        if command.startswith("find "):
            return {"stdout": self.remote_file + "\n", "stderr": "", "exit_code": 0}
        return {
            "stdout": "d41d8cd98f00b204e9800998ecf8427e\n",
            "stderr": "",
            "exit_code": 0,
        }


def test_sync_from_refuses_a_remote_path_outside_the_destination(
    monkeypatch, tmp_path
):
    remote_dir = tmp_path / "remote"
    remote_file = tmp_path / "escape.txt"
    local_dir = tmp_path / "local"

    class FakeTransfer:
        def __init__(self, _manager):
            pass

        def download(self, _server, _remote, local):
            with open(local, "w") as handle:
                handle.write("escaped")

    monkeypatch.setattr("cloudmesh.core.transfer.FileTransfer", FakeTransfer)
    manager = _EscapeServerManager(str(remote_dir), str(remote_file))

    results = DirectorySync(manager).sync_from("web1", str(remote_dir), str(local_dir))

    assert not (tmp_path / "escape.txt").exists()
    assert any(
        not result.get("success", True)
        and "unsafe" in result.get("error", "").lower()
        for result in results
    )


def test_log_search_quotes_the_pattern(monkeypatch):
    from cloudmesh.core import logagg

    monkeypatch.setattr(
        logagg,
        "_get_server",
        lambda _name: {"host": "h", "user": "root", "key": "", "os_type": "linux"},
    )
    seen = {}

    def fake_run(_host, _user, _key, command):
        seen["command"] = command
        return "line", 0

    monkeypatch.setattr(logagg, "_run_ssh", fake_run)
    pattern = "'; touch /tmp/pwn; #"

    logagg.get_logs("web1", search=pattern, lines=5)

    tokens = shlex.split(seen["command"])
    assert pattern in tokens
    assert tokens[0] == "grep"


def test_node_installer_uses_a_unique_remote_path_and_posix_sh(monkeypatch):
    import cloudmesh.main as main

    commands = []
    uploads = []

    class FakeServerManager:
        def execute(self, _name, command):
            commands.append(command)
            if command.startswith("mktemp "):
                return {
                    "stdout": "/tmp/cloudmesh-install.abc123\n",
                    "stderr": "",
                    "exit_code": 0,
                }
            return {"stdout": "", "stderr": "", "exit_code": 0}

    class FakeTransfer:
        def __init__(self, _manager):
            pass

        def upload(self, _name, local, remote):
            uploads.append((local, remote))
            assert Path(local).is_file()

    monkeypatch.setattr(main, "FileTransfer", FakeTransfer)

    result = main._run_node_installer(
        FakeServerManager(), "temp-server", "#!/bin/sh\necho install\n"
    )

    assert result["exit_code"] == 0
    assert uploads[0][1] == "/tmp/cloudmesh-install.abc123"
    assert any(command.startswith("sh /tmp/cloudmesh-install.abc123") for command in commands)
    assert not any(command.startswith("bash ") for command in commands)
    assert any(command == "rm -f /tmp/cloudmesh-install.abc123" for command in commands)
    assert not Path(uploads[0][0]).exists()


def test_node_installer_refuses_a_predictable_path_when_mktemp_fails(monkeypatch):
    import cloudmesh.main as main

    class FakeServerManager:
        def execute(self, _name, _command):
            return {"stdout": "", "stderr": "mktemp unavailable", "exit_code": 1}

    class FakeTransfer:
        def __init__(self, _manager):
            pass

        def upload(self, *_args):
            pytest.fail("must not upload to a predictable path")

    monkeypatch.setattr(main, "FileTransfer", FakeTransfer)

    with pytest.raises(RuntimeError, match="predictable temporary path"):
        main._run_node_installer(
            FakeServerManager(), "temp-server", "#!/bin/sh\necho install\n"
        )


def test_postgres_connection_arguments_are_shell_quoted(monkeypatch):
    from cloudmesh.core import database

    monkeypatch.setattr(
        database,
        "_get_server",
        lambda _name: {"host": "ssh", "user": "root", "key": ""},
    )
    seen = {}

    def fake_run(_host, _user, _key, command):
        seen["command"] = command
        return "", 0

    monkeypatch.setattr(database, "run_ssh", fake_run)
    host = "127.0.0.1; touch /tmp/pwn"
    user = "root; id"

    database.db_query("srv", "SELECT 1", db_type="postgres", host=host, user=user)

    tokens = shlex.split(seen["command"])
    assert tokens[tokens.index("-h") + 1] == host
    assert tokens[tokens.index("-U") + 1] == user


def test_mysql_config_escapes_newlines(monkeypatch):
    from cloudmesh.core import database

    command = database._mysql_cmd(
        "root", "127.0.0.1", 3306, "p\n!include /etc/passwd", None, "SELECT 1"
    )

    assert "\n!include" not in command


def test_postgres_passfile_cannot_inject_a_second_entry():
    from cloudmesh.core import database

    command = database._postgres_cmd(
        "root", "127.0.0.1", 5432, "p\n*:*:*:evil:x", None, "SELECT 1"
    )

    assert "\n*:*" not in command


def test_mysql_uses_mktemp_and_a_cleanup_trap():
    from cloudmesh.core import database

    command = database._mysql_cmd("root", "127.0.0.1", 3306, "p", None, "SELECT 1")
    assert "mktemp" in command
    assert "/tmp/.cm_my.conf" not in command
    assert "umask 077" in command
    assert "trap" in command
    assert 'rm -f "$remote_conf"' in command


def test_postgres_uses_mktemp_and_a_cleanup_trap():
    from cloudmesh.core import database

    command = database._postgres_cmd("root", "127.0.0.1", 5432, "p", None, "SELECT 1")
    assert "mktemp" in command
    assert "/tmp/.cm_pgpass" not in command
    assert "umask 077" in command
    assert "trap" in command
    assert 'rm -f "$remote_pgpass"' in command


@pytest.mark.parametrize("db_type, marker", [
    ("mysql", "/tmp/.cm_my.conf"),
    ("postgres", "/tmp/.cm_pgpass"),
])
def test_database_backup_uses_mktemp(db_type, marker, monkeypatch):
    from cloudmesh.core import database

    seen = {}
    monkeypatch.setattr(
        database,
        "_get_server",
        lambda _name: {"host": "h", "user": "root", "key": ""},
    )
    monkeypatch.setattr(
        database,
        "run_ssh",
        lambda _host, _user, _key, command: seen.update(command=command) or ("", 0),
    )

    result = database.db_backup("srv", "app", db_type=db_type, password="p")

    assert "Backup saved" in result
    assert "mktemp" in seen["command"]
    assert marker not in seen["command"]


def test_docker_deploy_quotes_environment_values(monkeypatch):
    from cloudmesh.core import docker

    monkeypatch.setattr(
        docker,
        "_get_server",
        lambda _name: {"host": "h", "user": "root", "key": "", "os_type": "linux"},
    )
    seen = {}

    def fake_run(_host, _user, _key, command):
        seen["command"] = command
        return "", 0

    monkeypatch.setattr(docker, "_run_ssh", fake_run)

    docker.docker_deploy(
        "web1",
        "nginx",
        name="app",
        ports=["8080:80"],
        env={"GREETING": "hello; touch /tmp/pwn"},
    )

    assert "GREETING=hello; touch /tmp/pwn" in shlex.split(seen["command"])


def test_docker_deploy_rejects_an_image_with_shell_metacharacters(monkeypatch):
    from cloudmesh.core import docker

    monkeypatch.setattr(
        docker,
        "_get_server",
        lambda _name: {"host": "h", "user": "root", "key": "", "os_type": "linux"},
    )
    monkeypatch.setattr(
        docker, "_run_ssh", lambda *_args: pytest.fail("command must not run")
    )

    result = docker.docker_deploy("web1", "nginx; touch /tmp/pwn")

    assert "invalid" in result.lower()


def test_api_stop_releases_the_listening_port():
    from cloudmesh.core.advanced import CloudMeshAPI

    api = CloudMeshAPI(port=0)
    port = api.start()
    assert port != 0

    api.stop()

    deadline = time.time() + 2
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                pass
        except OSError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("API port remained open after stop()")


def test_watcher_quotes_the_process_name(monkeypatch):
    from cloudmesh.core import watcher

    monkeypatch.setattr(
        watcher,
        "_get_server",
        lambda _name: {"host": "h", "user": "root", "key": ""},
    )
    seen = {}

    def fake_run(_host, _user, _key, command):
        seen["command"] = command
        return "1", 0

    monkeypatch.setattr(watcher, "_run_ssh", fake_run)
    process = "nginx'; touch /tmp/pwn; #"

    watcher.check_process("web1", process)

    assert process in shlex.split(seen["command"])
