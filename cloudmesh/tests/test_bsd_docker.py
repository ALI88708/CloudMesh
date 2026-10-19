import cloudmesh.core.docker as docker


def test_bsd_servers_get_an_explicit_message(monkeypatch):
    monkeypatch.setattr(docker, "_get_server", lambda n: {"os_type": "freebsd"})
    msg = docker.unsupported_on_bsd("bsd1")
    assert msg and "not supported" in msg.lower() and "freebsd" in msg.lower()


def test_linux_servers_are_untouched(monkeypatch):
    monkeypatch.setattr(docker, "_get_server", lambda n: {"os_type": "linux"})
    assert docker.unsupported_on_bsd("web1") is None


def test_unknown_server_is_untouched(monkeypatch):
    monkeypatch.setattr(docker, "_get_server", lambda n: None)
    assert docker.unsupported_on_bsd("ghost") is None


def test_docker_list_reports_bsd_targets_without_ssh(monkeypatch):
    monkeypatch.setattr(
        docker,
        "_load_config",
        lambda: {"servers": {"bsd1": {"host": "h", "os_type": "freebsd"}}},
    )
    calls = []

    def run(*a, **kw):
        calls.append(a)
        return "", 1

    monkeypatch.setattr(docker, "_run_ssh", run)
    results = docker.docker_list()
    assert calls == []
    assert "not supported" in results[0]["error"].lower()


def test_docker_manager_methods_return_the_message(monkeypatch):
    monkeypatch.setattr(docker, "_get_server", lambda n: {"os_type": "freebsd"})
    calls = []
    monkeypatch.setattr(docker, "_run_ssh", lambda *a: (calls.append(a), ("", 0))[1])
    mgr = docker.DockerManager()
    msg = mgr.container_stats("bsd1")
    assert "not supported" in msg.lower()
    assert calls == []
