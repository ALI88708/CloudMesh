from cloudmesh.core.sync import DirectorySync


class FakeServerManager:
    def __init__(self, os_type):
        self.os_type, self.commands = os_type, []

    def get_server_info(self, name):
        return {"os_type": self.os_type}

    def execute(self, name, cmd):
        self.commands.append(cmd)
        return {"stdout": "d41d8cd98f00b204e9800998ecf8427e\n", "stderr": "", "exit_code": 0}


def test_freebsd_uses_md5_q():
    mgr = FakeServerManager("freebsd")
    digest = DirectorySync(mgr)._remote_md5("bsd1", "/tmp/a file.txt")
    assert digest == "d41d8cd98f00b204e9800998ecf8427e"
    assert mgr.commands[0].startswith("md5 -q ")
    assert "'/tmp/a file.txt'" in mgr.commands[0]  # quoted


def test_linux_still_uses_md5sum():
    mgr = FakeServerManager("linux")
    DirectorySync(mgr)._remote_md5("web1", "/tmp/a file.txt")
    assert mgr.commands[0].startswith("md5sum ")
    assert "'/tmp/a file.txt'" in mgr.commands[0]
