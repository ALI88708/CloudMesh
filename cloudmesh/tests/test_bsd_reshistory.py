import cloudmesh.core.reshistory as rh


def test_freebsd_snapshot_uses_profile_commands(monkeypatch, tmp_path):
    monkeypatch.setattr(rh, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        rh, "_get_server", lambda n: {"host": "h", "user": "root", "key": "", "os_type": "freebsd"}
    )
    vmstat = " r b w avm fre flt re pi po fr sr in sy cs us sy id\n 1 0 0 1 1 1 0 0 0 0 0 0 1 1 1 1 95\n"
    df_out = "Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/ada0p2 1000000 400000 600000 40% /\n"

    def run(host, user, key, cmd):
        if "vmstat" in cmd:
            return vmstat, 0
        if "hw.physmem" in cmd:
            return "8589934592\n4096\n500000\n300000\n", 0
        return df_out, 0  # df -kP output

    monkeypatch.setattr(rh, "_run_ssh", run)
    rh.snapshot("bsd1")
    entry = rh.show_history("bsd1")[-1]
    assert entry["cpu"] == 5.0
    assert entry["disk"] == 40
    assert entry["ram"] > 0


def test_linux_snapshot_uses_the_linux_commands(monkeypatch, tmp_path):
    monkeypatch.setattr(rh, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        rh, "_get_server", lambda n: {"host": "h", "user": "root", "key": "", "os_type": "linux"}
    )
    seen = []

    def run(host, user, key, cmd):
        seen.append(cmd)
        if "/proc/stat" in cmd:
            return "42.5", 0
        if "/proc/meminfo" in cmd:
            return '{"total_gb": 8.0, "used_gb": 4.0, "free_gb": 4.0, "percent": 50.0}', 0
        return '{"total_gb": 100.0, "used_gb": 60.0, "free_gb": 40.0, "percent": 60.0}', 0

    monkeypatch.setattr(rh, "_run_ssh", run)
    rh.snapshot("web1")
    entry = rh.show_history("web1")[-1]
    assert entry["cpu"] == 42.5
    assert entry["ram"] == 50.0
    assert entry["disk"] == 60
    assert len(seen) == 3


def test_snapshot_skips_a_server_whose_metrics_do_not_parse(monkeypatch, tmp_path):
    monkeypatch.setattr(rh, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        rh, "_get_server", lambda n: {"host": "h", "user": "root", "key": "", "os_type": "freebsd"}
    )

    def run(host, user, key, cmd):
        return "", 1

    monkeypatch.setattr(rh, "_run_ssh", run)
    rh.snapshot("bsd1")
    assert rh.show_history("bsd1") == "No history for bsd1"
