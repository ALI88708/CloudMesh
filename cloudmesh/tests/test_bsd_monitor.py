from cloudmesh.core.monitor import ResourceMonitor


class FakeServerManager:
    def __init__(self, os_type, stdout):
        self.os_type = os_type
        self.stdout = stdout
        self.commands = []

    def get_server_info(self, name):
        return {"os_type": self.os_type}

    def execute(self, name, cmd):
        self.commands.append(cmd)
        return {"stdout": self.stdout, "stderr": "", "exit_code": 0}


def test_freebsd_ram_uses_the_profile_command():
    mgr = FakeServerManager("freebsd", "8589934592\n4096\n500000\n300000\n")
    mon = ResourceMonitor(mgr)
    ram = mon.get_ram("bsd1")
    assert ram["total_gb"] == 8.0
    assert "hw.physmem" in mgr.commands[0]


def test_unknown_os_type_still_uses_the_linux_command():
    mgr = FakeServerManager(None, "42.0")
    mon = ResourceMonitor(mgr)
    assert mon.get_cpu("legacy") == 42.0
    assert "/proc/stat" in mgr.commands[0]
