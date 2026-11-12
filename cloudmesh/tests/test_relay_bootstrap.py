import json
from types import SimpleNamespace

import pytest

from cloudmesh.core.node_relay import (
    DEFAULT_POOL,
    NodeRelayStore,
    RelayError,
    RelayProfileStore,
    RelayProvisioner,
    restart_agent,
)

RELAY_URL = "relay.test:9997"
ADMIN_KEY = "11" * 32
RELAY_FP = "22" * 32


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
        return ("", 0)

    def upload_bytes(self, host, user, key, remote_path, data, mode=0o600, port=22):
        if self.fail_upload:
            raise OSError("upload failed")
        self.files[remote_path] = (data, mode)


class FakeAdminClient:
    def __init__(self, url, admin_key, relay_fingerprint, ca_file=None, timeout=10.0):
        self.url = url
        self.enrolled = []
        self.revoked = []

    def enroll(self, relay_id, token, pool=DEFAULT_POOL):
        self.enrolled.append((relay_id, token, pool))
        return {"data": {"success": True}}

    def revoke(self, relay_id):
        self.revoked.append(relay_id)
        return {"data": {"success": True}}


def make_provisioner(tmp_path, ssh, admin=None):
    profiles = RelayProfileStore(tmp_path)
    nodes = NodeRelayStore(tmp_path)
    profiles.set(RELAY_URL, ADMIN_KEY, RELAY_FP)
    admin = admin or FakeAdminClient(RELAY_URL, ADMIN_KEY, RELAY_FP)
    provisioner = RelayProvisioner(
        profiles,
        nodes,
        ssh=ssh,
        base_dir=tmp_path,
        admin_client_factory=lambda *a, **k: admin,
    )
    return provisioner, SimpleNamespace(profiles=profiles, nodes=nodes, admin=admin)


def test_enable_ssh_uploads_private_files_and_saves_sidecar(tmp_path):
    ssh = FakeSSH()
    provisioner, stores = make_provisioner(tmp_path, ssh)
    result = provisioner.enable_ssh(
        "web-1",
        RELAY_URL,
        ssh_host="10.0.0.5",
        ssh_user="root",
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
        provisioner.enable_ssh(
            "web-1",
            RELAY_URL,
            ssh_host="10.0.0.5",
            ssh_user="root",
            verify=lambda *a: True,
        )
    assert stores.nodes.get("web-1") is None


def test_enable_ssh_rolls_back_on_verification_failure(tmp_path):
    ssh = FakeSSH()
    provisioner, stores = make_provisioner(tmp_path, ssh)
    with pytest.raises(RelayError, match="verification"):
        provisioner.enable_ssh(
            "web-1",
            RELAY_URL,
            ssh_host="10.0.0.5",
            ssh_user="root",
            verify=lambda *a: False,
            timeout=0,
        )
    assert stores.nodes.get("web-1") is None
    assert stores.admin.revoked


def test_enable_ssh_keeps_the_config_when_the_restart_fails(tmp_path, capsys):
    class NoUnitSSH(FakeSSH):
        def run(self, host, user, key, command, port=22, timeout=30):
            self.commands.append(command)
            if "restart" in command or ".sh" in command:
                return ("not found", 1)
            return ("", 0)

    ssh = NoUnitSSH()
    provisioner, stores = make_provisioner(tmp_path, ssh)
    result = provisioner.enable_ssh(
        "web-1",
        RELAY_URL,
        ssh_host="10.0.0.5",
        ssh_user="root",
        verify=lambda *a: True,
    )
    output = capsys.readouterr().out
    assert result["restart_ok"] is False
    assert "restart" in output.lower()
    assert stores.nodes.get("web-1") is not None


def test_restart_command_prefers_systemd_then_rcd_then_service():
    ssh = FakeSSH()
    assert restart_agent(ssh, "h", "u", None) == (
        True,
        "systemctl restart cloudmesh-node",
    )
    ssh2 = FakeSSH()
    ssh2.run = lambda *a, **k: ("not found", 1)
    assert "rc.d" in restart_agent(ssh2, "h", "u", None)[1]


def test_enable_local_writes_node_config_and_returns_import(tmp_path):
    provisioner, _ = make_provisioner(tmp_path, FakeSSH())
    result = provisioner.enable_local("web-1", RELAY_URL, pool=2)
    node_file = tmp_path / ".cloudmesh-node" / ".node_relay.json"
    assert json.loads(node_file.read_text())["pool"] == 2
    assert result["import_command"].startswith("cm node relay import")


def test_import_local_enrolls_and_saves_the_sidecar(tmp_path):
    provisioner, stores = make_provisioner(tmp_path, FakeSSH())
    provisioner.import_local(
        "web-1", RELAY_URL, "ab" * 16, "cd" * 32, "ef" * 32, "11" * 32
    )
    assert stores.nodes.get("web-1")["node_fingerprint"] == "ef" * 32


def test_disable_local_removes_the_node_config(tmp_path):
    provisioner, _ = make_provisioner(tmp_path, FakeSSH())
    provisioner.enable_local("web-1", RELAY_URL)
    provisioner.disable_local("web-1", RELAY_URL)
    assert not (tmp_path / ".cloudmesh-node" / ".node_relay.json").exists()
