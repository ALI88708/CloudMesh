from cloudmesh.core.osprofile import LinuxProfile, WindowsProfile, get_profile


def test_unknown_and_missing_os_type_fall_back_to_linux():
    assert get_profile(None).key == "linux"
    assert get_profile("").key == "linux"
    assert get_profile("solaris").key == "linux"
    assert get_profile("FREEBSD ").key == "linux"  # not registered yet


def test_linux_profile_commands_match_todays_strings():
    p = LinuxProfile()
    assert "/proc/stat" in p.cpu_cmd()
    assert "/proc/meminfo" in p.ram_cmd()
    assert "statvfs" in p.disk_cmd()
    assert p.parse_cpu("12.5") == 12.5
    assert p.parse_cpu("garbage") is None
    assert p.parse_ram('{"total_gb": 8.0, "used_gb": 2.0, "free_gb": 6.0, "percent": 25.0}')["percent"] == 25.0


def test_windows_profile_uses_powershell():
    p = WindowsProfile()
    assert "powershell" in p.cpu_cmd().lower()
