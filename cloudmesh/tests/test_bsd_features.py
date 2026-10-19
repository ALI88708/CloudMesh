from cloudmesh.core import features


class FakeServerManager:
    def __init__(self, os_type, stdout=""):
        self.os_type, self.stdout, self.commands = os_type, stdout, []

    def get_server_info(self, name):
        return {"os_type": self.os_type}

    def execute(self, name, cmd):
        self.commands.append(cmd)
        return {"stdout": self.stdout, "stderr": "", "exit_code": 0}


def test_freebsd_top_parses_and_sorts_in_python():
    ps = "  PID  %CPU %MEM COMMAND\n 11  5.0  1.0 nginx\n 22 40.5  2.0 python\n"
    mgr = FakeServerManager("freebsd", ps)
    procs = features.get_top_processes(mgr, "bsd1", limit=1, sort_by="cpu")
    assert procs == [{"pid": "22", "usage": "40.5", "name": "python"}]
    assert "ps -axo" in mgr.commands[0]


def test_freebsd_top_sorts_by_memory_when_asked():
    ps = "  PID  %CPU %MEM COMMAND\n 11  50.0  1.0 nginx\n 22 40.5 30.0 python\n"
    mgr = FakeServerManager("freebsd", ps)
    procs = features.get_top_processes(mgr, "bsd1", limit=1, sort_by="ram")
    assert procs == [{"pid": "22", "usage": "30.0", "name": "python"}]


def test_freebsd_disk_detail_keeps_every_data_row():
    df = (
        "Filesystem   Size  Used Avail Capacity  Mounted on\n"
        "/dev/ada0p2 100G  40G   60G       40%  /\n"
        "/dev/ada0p3  10G   1G    9G       10%  /var\n"
    )
    mgr = FakeServerManager("freebsd", df)
    disks = features.get_disk_detail(mgr, "bsd1")
    assert disks == [
        {
            "device": "/dev/ada0p2",
            "size": "100G",
            "used": "40G",
            "avail": "60G",
            "use%": "40%",
            "mount": "/",
        },
        {
            "device": "/dev/ada0p3",
            "size": "10G",
            "used": "1G",
            "avail": "9G",
            "use%": "10%",
            "mount": "/var",
        },
    ]
    assert mgr.commands[0].strip() == "df -h"


def test_freebsd_network_and_who_use_bsd_tools():
    net = FakeServerManager("freebsd", "em0: flags=8843<UP>")
    features.get_network_info(net, "bsd1")
    assert net.commands[0].strip().startswith("ifconfig -a")
    who = FakeServerManager("freebsd", "root ttyv0")
    features.get_logged_users(who, "bsd1")
    assert who.commands[0].strip() == "who"


def test_freebsd_logs_default_to_messages():
    mgr = FakeServerManager("freebsd", "a log line")
    out = features.get_recent_logs(mgr, "bsd1", lines=5)
    assert out == "a log line"
    assert "/var/log/messages" in mgr.commands[0]
    assert "/var/log/syslog" not in mgr.commands[0]


def test_freebsd_uptime_has_no_gnu_dash_p():
    mgr = FakeServerManager("freebsd", "10:00 up 3 days")
    features.get_uptime(mgr, "bsd1")
    assert mgr.commands[0].strip() == "uptime"


def test_linux_keeps_todays_commands():
    top = FakeServerManager("linux", "  7  1.0  0.5 init\n")
    features.get_top_processes(top, "web1", limit=3)
    assert "--sort=-pcpu" in top.commands[0]
    disk = FakeServerManager(None, "")
    assert features.get_disk_detail(disk, "legacy") == []
    assert "--output=source,size,used,avail,pcent,target" in disk.commands[0]


def test_profile_lookup_survives_a_broken_server_record():
    class Broken(FakeServerManager):
        def get_server_info(self, name):
            raise KeyError(name)

    mgr = Broken(None, "line")
    assert features.get_recent_logs(mgr, "ghost", lines=1) == "line"
    assert "/var/log/syslog" in mgr.commands[0]
