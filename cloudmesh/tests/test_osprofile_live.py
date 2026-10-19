"""Live command checks for the BSD profiles.

These run only on a real FreeBSD host (the GitHub Actions FreeBSD VM in
`.github/workflows/bsd.yml`); everywhere else they are skipped. They exist
because the FreeBSD OIDs and `vmstat`/`df` column layouts are the one part of
the profile layer that fixtures cannot prove.
"""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "freebsd", reason="FreeBSD only")


@pytest.mark.parametrize("os_type", ["freebsd"])
def test_commands_work_against_the_real_freebsd_host(os_type):
    import subprocess

    from cloudmesh.core.osprofile import get_profile

    p = get_profile(os_type)
    cpu = p.parse_cpu(subprocess.run(p.cpu_cmd(), shell=True, capture_output=True, text=True).stdout)
    ram = p.parse_ram(subprocess.run(p.ram_cmd(), shell=True, capture_output=True, text=True).stdout)
    disk = p.parse_disk(subprocess.run(p.disk_cmd(), shell=True, capture_output=True, text=True).stdout)
    assert cpu is None or 0.0 <= cpu <= 100.0
    assert ram and ram["total_gb"] > 0 and 0.0 <= ram["percent"] <= 100.0
    assert disk and disk["total_gb"] > 0
