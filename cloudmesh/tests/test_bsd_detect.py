import pytest

from cloudmesh.core.server import ServerManager


class DetectHarness(ServerManager):
    """ServerManager with the SSH call and storage side effects stubbed out."""

    def __init__(self, uname):
        self._uname = uname

    def execute(self, name, cmd):
        return {"stdout": self._uname, "stderr": "", "exit_code": 0}

    def _save(self):
        pass

    def _ensure_mirror(self, name):
        pass

    def get_server_info(self, name):
        return {}


@pytest.mark.parametrize(
    "uname,expected",
    [
        ("Linux\n", "linux"),
        ("Darwin\n", "linux"),
        ("FreeBSD\n", "freebsd"),
        ("OpenBSD\n", "openbsd"),
        ("NetBSD\n", "netbsd"),
        ("MINGW64_NT-10.0\n", "windows"),
    ],
)
def test_detect_os_maps_uname_families(uname, expected):
    mgr = DetectHarness(uname)
    mgr.storage = type("StorageStub", (), {"update_server_os_type": lambda self, n, o: None})()
    mgr.config = {"servers": {"node1": {}}}
    assert mgr.detect_os("node1") == expected
