import cloudmesh.core.logagg as logagg


def _freebsd_record():
    return {"host": "h", "user": "root", "key": "", "os_type": "freebsd"}


def test_freebsd_default_source_is_messages(monkeypatch):
    monkeypatch.setattr(logagg, "_get_server", lambda n: _freebsd_record())
    seen = {}

    def run(host, user, key, cmd):
        seen["cmd"] = cmd
        return "line", 0

    monkeypatch.setattr(logagg, "_run_ssh", run)
    logagg.get_logs("bsd1", lines=5)
    assert "/var/log/messages" in seen["cmd"]
    assert "/var/log/syslog" not in seen["cmd"]


def test_linux_default_source_is_syslog(monkeypatch):
    monkeypatch.setattr(
        logagg, "_get_server", lambda n: {"host": "h", "user": "root", "key": "", "os_type": "linux"}
    )
    seen = {}

    def run(host, user, key, cmd):
        seen["cmd"] = cmd
        return "line", 0

    monkeypatch.setattr(logagg, "_run_ssh", run)
    logagg.get_logs("web1", lines=5)
    assert "/var/log/syslog" in seen["cmd"]


def test_record_without_os_type_defaults_to_linux(monkeypatch):
    monkeypatch.setattr(logagg, "_get_server", lambda n: {"host": "h", "user": "root", "key": ""})
    seen = {}

    def run(host, user, key, cmd):
        seen["cmd"] = cmd
        return "line", 0

    monkeypatch.setattr(logagg, "_run_ssh", run)
    logagg.get_logs("legacy", lines=5)
    assert "/var/log/syslog" in seen["cmd"]


def test_explicit_path_still_wins(monkeypatch):
    monkeypatch.setattr(logagg, "_get_server", lambda n: _freebsd_record())
    seen = {}

    def run(host, user, key, cmd):
        seen["cmd"] = cmd
        return "line", 0

    monkeypatch.setattr(logagg, "_run_ssh", run)
    logagg.get_logs("bsd1", "/var/log/custom.log", lines=5)
    assert "/var/log/custom.log" in seen["cmd"]
    assert "/var/log/messages" not in seen["cmd"]


def test_follow_log_defaults_from_profile(monkeypatch):
    monkeypatch.setattr(logagg, "_get_server", lambda n: _freebsd_record())
    captured = {}

    class FakeProc:
        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            self.stdout = self

        def readline(self):
            return ""

        def terminate(self):
            pass

    monkeypatch.setattr(logagg.subprocess, "Popen", FakeProc)
    logagg.follow_log("bsd1")
    assert any("/var/log/messages" in part for part in captured["cmd"])
