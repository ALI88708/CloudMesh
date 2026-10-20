import json
import os
import sys
import urllib.error
import urllib.request
from unittest.mock import Mock

import pytest

from cloudmesh import main as cloudmesh_main
from cloudmesh.core import advanced
from cloudmesh.core.advanced import CloudMeshAPI, load_api_key_file


@pytest.fixture(autouse=True)
def _isolate_command_log(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))


class FakeRequest:
    def __init__(self, path, headers=None):
        self.path = path
        self.headers = headers or {}


def test_exec_is_disabled_by_default():
    api = CloudMeshAPI(api_key="k")
    result = api._handle(FakeRequest("/api/exec/s?cmd=whoami", {"X-Api-Key": "k"}))
    assert isinstance(result, tuple)
    assert result[1] == 403
    assert "disabled" in result[0]["error"].lower()


def test_exec_can_be_enabled(tmp_path):
    class ServerManager:
        def list_servers(self):
            return ["s"]

        def execute(self, _server, command):
            return {"stdout": command, "exit_code": 0}

    api = CloudMeshAPI(api_key="k", enable_exec=True)
    api.server_mgr = ServerManager()
    result = api._handle(FakeRequest("/api/exec/s?cmd=uptime", {"X-Api-Key": "k"}))
    assert result["output"] == "uptime"
    entries = json.loads((tmp_path / "command_log.json").read_text())
    assert entries[-1]["command"] == "api:exec"
    assert entries[-1]["args"] == "s: uptime"


def test_exec_allowlist_is_exact():
    class ServerManager:
        def list_servers(self):
            return ["s"]

        def execute(self, _server, command):
            return {"stdout": command, "exit_code": 0}

    api = CloudMeshAPI(api_key="k", enable_exec=True, exec_allowlist={"uptime"})
    api.server_mgr = ServerManager()
    assert api._handle(FakeRequest("/api/exec/s?cmd=uptime", {"X-Api-Key": "k"}))["output"] == "uptime"
    blocked = api._handle(FakeRequest("/api/exec/s?cmd=uptime%3Bid", {"X-Api-Key": "k"}))
    assert isinstance(blocked, tuple)
    assert blocked[1] == 403


def test_api_sends_security_headers_on_success():
    api = CloudMeshAPI(api_key="k", port=0)
    port = api.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/status",
            headers={"X-Api-Key": "k"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["Cache-Control"] == "no-store"
            assert response.headers["X-Frame-Options"] == "DENY"
    finally:
        api.stop()


def test_api_sends_security_headers_on_401():
    api = CloudMeshAPI(api_key="k", port=0)
    port = api.start()
    try:
        request = urllib.request.Request(f"http://127.0.0.1:{port}/api/status")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(request, timeout=2)
        assert exc.value.headers["X-Content-Type-Options"] == "nosniff"
    finally:
        api.stop()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission check")
def test_api_key_file_requires_owner_only_mode(tmp_path):
    key_file = tmp_path / "api.key"
    key_file.write_text("a" * 64)
    key_file.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        load_api_key_file(key_file)
    key_file.chmod(0o600)
    assert load_api_key_file(key_file) == "a" * 64


def test_auth_failure_logging_is_rate_limited(monkeypatch):
    api = CloudMeshAPI(api_key="k")
    warning = Mock()
    monkeypatch.setattr(advanced.logger, "warning", warning)
    now = [1000.0]
    monkeypatch.setattr(advanced.time, "monotonic", lambda: now[0])

    api._log_auth_failure("1.2.3.4")
    api._log_auth_failure("1.2.3.4")
    assert warning.call_count == 1

    now[0] += 61
    api._log_auth_failure("1.2.3.4")
    assert warning.call_count == 2

    for index in range(1100):
        api._log_auth_failure(f"10.0.{index // 256}.{index % 256}")
    assert len(api._auth_failures) <= 1024


def test_allow_command_requires_enable_exec(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["cloudmesh", "api", "--allow-command", "uptime"]
    )

    with pytest.raises(SystemExit) as exc:
        cloudmesh_main.main()

    assert exc.value.code == 2
    assert "--enable-exec" in capsys.readouterr().out


def test_api_key_file_is_used_and_not_printed(tmp_path, monkeypatch, capsys):
    key_file = tmp_path / "api.key"
    key = "b" * 64
    key_file.write_text(key)
    if os.name != "nt":
        key_file.chmod(0o600)

    seen = {}

    class FakeAPI:
        def __init__(self, *args, **kwargs):
            seen.update(kwargs)
            self.api_key = kwargs.get("api_key")

        def start(self):
            return 8124

        def stop(self):
            pass

    monkeypatch.setattr(cloudmesh_main, "CloudMeshAPI", FakeAPI)
    monkeypatch.setattr(cloudmesh_main, "_load_node_keys", lambda: {})
    monkeypatch.setattr(cloudmesh_main, "init_components", lambda: tuple([None] * 11))
    monkeypatch.setattr(
        cloudmesh_main.time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["cloudmesh", "api", "--api-key-file", str(key_file), "--port", "8124"],
    )

    cloudmesh_main.main()

    output = capsys.readouterr().out
    assert seen["api_key"] == key
    assert seen["enable_exec"] is False
    assert key not in output
    assert "Using API key from" in output
