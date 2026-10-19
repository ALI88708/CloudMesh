"""OS-specific command strings and parsers, keyed by ``os_type``.

The profile layer is the single place where a platform's tools are named:
monitoring, features, deploy, sync, logs and audit ask for a profile and do
not branch on the OS themselves. Anything that does not match a registered
key falls back to Linux, which is what legacy configs assume.
"""

import json


LINUX_CPU_CMD = """python3 -c "
import os, time
def get_cpu():
    with open('/proc/stat') as f:
        line = f.readline()
    parts = line.split()[1:]
    total = sum(int(p) for p in parts)
    idle = int(parts[3])
    return total, idle
t1, i1 = get_cpu()
time.sleep(1)
t2, i2 = get_cpu()
total = t2 - t1
idle = i2 - i1
print(round((1 - idle/total)*100, 1) if total > 0 else 0)
" """

LINUX_RAM_CMD = """python3 -c "
import json
with open('/proc/meminfo') as f:
    lines = f.readlines()
info = {}
for line in lines:
    parts = line.split()
    info[parts[0].rstrip(':')] = int(parts[1])
total = info['MemTotal'] / 1048576
free = info['MemAvailable'] / 1048576
used = total - free
pct = round((used/total)*100, 1) if total > 0 else 0
print(json.dumps({'total_gb': round(total,1), 'used_gb': round(used,1), 'free_gb': round(free,1), 'percent': pct}))
" """

LINUX_DISK_CMD = """python3 -c "
import os, json
st = os.statvfs('/')
total = (st.f_blocks * st.f_frsize) / (1024**3)
free = (st.f_bavail * st.f_frsize) / (1024**3)
used = total - free
pct = round((used/total)*100, 1) if total > 0 else 0
print(json.dumps({'total_gb': round(total,1), 'used_gb': round(used,1), 'free_gb': round(free,1), 'percent': pct}))
" """

WINDOWS_CPU_CMD = """powershell -Command "(Get-Counter '\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue" """

WINDOWS_RAM_CMD = """powershell -Command "$os=Get-CimInstance Win32_OperatingSystem; $t=[math]::Round($os.TotalVisibleMemorySize/1MB,1); $f=[math]::Round($os.FreePhysicalMemory/1MB,1); $u=$t-$f; $p=[math]::Round(($u/$t)*100,1); @{total_gb=$t;used_gb=$u;free_gb=$f;percent=$p}|ConvertTo-Json" """

WINDOWS_DISK_CMD = """powershell -Command "$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\"; $t=[math]::Round($d.Size/1GB,1); $f=[math]::Round($d.FreeSpace/1GB,1); $u=$t-$f; $p=[math]::Round(($u/$t)*100,1); @{total_gb=$t;used_gb=$u;free_gb=$f;percent=$p}|ConvertTo-Json" """


class OsProfile:
    """Command strings and output parsers for one operating system."""

    key = "linux"
    family = "posix"

    def cpu_cmd(self):
        return LINUX_CPU_CMD

    def ram_cmd(self):
        return LINUX_RAM_CMD

    def disk_cmd(self):
        return LINUX_DISK_CMD

    def parse_cpu(self, raw):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def parse_ram(self, raw):
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None

    def parse_disk(self, raw):
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None


class LinuxProfile(OsProfile):
    key = "linux"
    family = "posix"


class WindowsProfile(OsProfile):
    key = "windows"
    family = "windows"

    def cpu_cmd(self):
        return WINDOWS_CPU_CMD

    def ram_cmd(self):
        return WINDOWS_RAM_CMD

    def disk_cmd(self):
        return WINDOWS_DISK_CMD


_PROFILES = {
    "linux": LinuxProfile(),
    "windows": WindowsProfile(),
}


def get_profile(os_type):
    """Return the profile for *os_type*; unknown values fall back to Linux."""
    value = (os_type or "linux").strip().lower()
    return _PROFILES.get(value, _PROFILES["linux"])
