from cloudmesh.core.deploy import PackageDeployer


class FakeServerManager:
    def __init__(self, responses, os_type="freebsd"):
        self.responses = responses  # cmd substring -> stdout
        self.os_type = os_type
        self.commands = []

    def get_server_info(self, name):
        return {"os_type": self.os_type}

    def list_servers(self):
        return ["bsd1"]

    def execute(self, name, cmd):
        self.commands.append(cmd)
        for needle, out in self.responses.items():
            if needle in cmd:
                return {"stdout": out, "stderr": "", "exit_code": 0}
        return {"stdout": "", "stderr": "", "exit_code": 1}


def test_freebsd_uses_pkg_and_doas_when_sudo_absent():
    mgr = FakeServerManager(
        {"which pkg": "pkg\n", "which doas": "doas\n", "which sudo": "", "pkg info -e": "installed"}
    )
    pd = PackageDeployer(mgr)
    assert pd._detect_package_manager("bsd1") == "pkg"
    assert pd.check_installed("bsd1", "nginx") is True
    pd.install("bsd1", "nginx")
    assert any(c.startswith("doas pkg install -y nginx") for c in mgr.commands)


def test_install_runs_without_a_privilege_tool_when_neither_exists():
    mgr = FakeServerManager({"which pkg": "pkg\n"})
    PackageDeployer(mgr).install("bsd1", "nginx")
    assert any(c.startswith("pkg install -y nginx") for c in mgr.commands)


def test_openbsd_installs_the_flavoured_python_package():
    mgr = FakeServerManager(
        {"which pkg_add": "pkg_add\n", "which doas": "doas\n"}, os_type="openbsd"
    )
    PackageDeployer(mgr).install_python(["obsd1"])
    assert any("doas pkg_add python%3" in c for c in mgr.commands)


def test_run_script_uses_sh_on_bsd(monkeypatch):
    uploaded = {"run": []}

    class FakeTransfer:
        def __init__(self, mgr): ...

        def upload(self, server, local, remote): uploaded["remote"] = remote

    import cloudmesh.core.transfer as transfer_mod
    monkeypatch.setattr(transfer_mod, "FileTransfer", FakeTransfer)

    mgr = FakeServerManager({})
    mgr.execute = lambda name, cmd: (
        uploaded["run"].append(cmd),
        {"stdout": "ok", "stderr": "", "exit_code": 0},
    )[1]
    PackageDeployer(mgr).run_script("bsd1", "echo hi", "s.sh")
    assert "sh /tmp/s.sh" in [cmd.strip() for cmd in uploaded["run"]]
