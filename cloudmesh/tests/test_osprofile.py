from cloudmesh.core.osprofile import LinuxProfile, WindowsProfile, get_profile


def test_unknown_and_missing_os_type_fall_back_to_linux():
    assert get_profile(None).key == "linux"
    assert get_profile("").key == "linux"
    assert get_profile("solaris").key == "linux"
    assert get_profile("FREEBSD ").key == "freebsd"  # case/space-insensitive lookup


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


FREEBSD_VMSTAT = """ procs      memory      page                    disks     faults         cpu
 r b w     avm    fre  flt  re  pi  po  fr   sr da0 pass0     in   sy  cs us sy id
 1 0 0  123456  78901   12   0   0   0   4    0   0   0    231  456  12  3  2 95
"""

OPENBSD_VMSTAT = """procs   memory       page                       disks     faults      cpu
 r b w  avm    fre    flt  re  pi  po    fr   sr cd0 sd0     in   sy   cs us sy id
 1 0 0 3321   9876    123  10   2   1    10    5   0   0    321  654   23  8  5 87
"""

NETBSD_VMSTAT = """procs   memory       page                       disks     faults      cpu
 r b w  avm    fre    flt  re  pi  po    fr   sr cd0 sd0     in   sy   cs us sy id
 1 0 0 3321   9876    123  10   2   1    10    5   0   0    321  654   23  8  5 91
"""

DF_POSIX = """Filesystem  1024-blocks  Used  Available  Capacity  Mounted on
/dev/ada0p2     1000000  400000     600000       40%  /
"""


def test_freebsd_cpu_parses_idle_from_last_vmstat_row():
    p = get_profile("freebsd")
    assert p.key == "freebsd"
    assert p.family == "posix"
    assert "vmstat 1 2" in p.cpu_cmd()
    assert p.parse_cpu(FREEBSD_VMSTAT) == 5.0


def test_freebsd_ram_command_and_parser():
    p = get_profile("freebsd")
    assert "hw.physmem" in p.ram_cmd()
    assert "v_free_count" in p.ram_cmd()
    ram = p.parse_ram("8589934592\n4096\n500000\n300000\n")
    assert ram["total_gb"] == 8.0
    assert ram["percent"] > 0
    assert ram["free_gb"] > 0


def test_openbsd_profile_registered_with_its_own_commands():
    p = get_profile("openbsd")
    assert p.key == "openbsd" and p.family == "posix"
    assert "vmstat 1 2" in p.cpu_cmd()
    assert p.parse_cpu(OPENBSD_VMSTAT) == 13.0
    assert "hw.physmem hw.pagesize vm.uvmexp.free" in p.ram_cmd()
    ram = p.parse_ram("17179869184\n4096\n1000000\n")
    assert ram["total_gb"] == 16.0 and ram["percent"] > 0


def test_netbsd_profile_registered_with_its_own_commands():
    p = get_profile("netbsd")
    assert p.key == "netbsd" and p.family == "posix"
    assert p.parse_cpu(NETBSD_VMSTAT) == 9.0
    assert "hw.physmem64" in p.ram_cmd()
    ram = p.parse_ram("17179869184\n4096\n1000000\n200000\n")
    assert ram["total_gb"] == 16.0 and ram["percent"] > 0


def test_bsd_disk_parser_reads_df_kp_output():
    p = get_profile("freebsd")
    assert "df -kP" in p.disk_cmd()
    disk = p.parse_disk(DF_POSIX)
    assert disk["percent"] == 40.0
    assert disk["total_gb"] == 1.0


def test_bsd_parsers_return_none_instead_of_raising():
    p = get_profile("freebsd")
    assert p.parse_cpu("garbage") is None
    assert p.parse_cpu("") is None
    assert p.parse_ram("") is None
    assert p.parse_ram("only-one-line\n") is None
    assert p.parse_disk("Filesystem\n") is None
