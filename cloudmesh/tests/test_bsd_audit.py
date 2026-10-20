from cloudmesh.core.advanced import audit_server


class FakeServerManager:
    def __init__(self, os_type):
        self.os_type, self.commands = os_type, []

    def get_server_info(self, name):
        return {"os_type": self.os_type}

    def execute(self, name, cmd):
        self.commands.append(cmd)
        return {"stdout": "no", "stderr": "", "exit_code": 0}


def test_freebsd_audit_never_runs_systemd_commands():
    mgr = FakeServerManager("freebsd")
    checks = audit_server(mgr, "bsd1")
    assert any("pfctl" in c for c in mgr.commands)
    assert not any("systemctl" in c for c in mgr.commands)
    assert checks and all({"check", "result", "risk"} <= set(c) for c in checks)


def test_linux_audit_keeps_its_eight_checks_in_order():
    mgr = FakeServerManager("linux")
    checks = audit_server(mgr, "web1")
    assert [c["check"] for c in checks] == [
        "SSH Root Login",
        "Firewall Status",
        "Open Ports",
        "Failed Logins",
        "Users with Shell",
        "Disk Encrypted",
        "Auto Updates",
        "SSH Key Auth",
    ]
    assert any("systemctl" in c for c in mgr.commands)
    assert any("ufw status" in c for c in mgr.commands)


def test_openbsd_uses_syspatch_and_authlog():
    mgr = FakeServerManager("openbsd")
    audit_server(mgr, "obsd1")
    assert any("syspatch" in c for c in mgr.commands)
    assert any("/var/log/authlog" in c for c in mgr.commands)
    assert not any("geli" in c for c in mgr.commands)
    assert not any("systemctl" in c for c in mgr.commands)


def test_netbsd_reports_no_automatic_updates():
    mgr = FakeServerManager("netbsd")
    audit_server(mgr, "nbsd1")
    assert any("Not configured" in c for c in mgr.commands)
    assert not any("systemctl" in c for c in mgr.commands)
