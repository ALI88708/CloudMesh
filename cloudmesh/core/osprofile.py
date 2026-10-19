"""OS-specific command strings and parsers, keyed by ``os_type``.

The profile layer is the single place where a platform's tools are named:
monitoring, features, deploy, sync, logs and audit ask for a profile and do
not branch on the OS themselves. Anything that does not match a registered
key falls back to Linux, which is what legacy configs assume.
"""

import json
import shlex


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


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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

    def uptime_cmd(self):
        return "uptime -p 2>/dev/null || uptime"

    def top_cmd(self, sort_by, limit):
        flag = "-o %cpu" if sort_by == "cpu" else "-o %mem"
        column = "pcpu" if sort_by == "cpu" else "pmem"
        return f"ps {flag} --sort=-{column} --no-headers -A | head -n {limit}"

    def parse_top(self, raw, sort_by, limit):
        procs = []
        for line in (raw or "").strip().split("\n"):
            parts = line.split()
            if len(parts) >= 2:
                procs.append({"pid": parts[0], "usage": parts[1], "name": " ".join(parts[2:])})
        return procs

    def disk_detail_cmd(self):
        return (
            "df -h --output=source,size,used,avail,pcent,target 2>/dev/null | grep -E '^/'"
            " || df -h 2>/dev/null | grep -E '^/'"
        )

    def parse_disk_detail(self, raw):
        disks = []
        for line in (raw or "").strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 6:
                disks.append(
                    {
                        "device": parts[0],
                        "size": parts[1],
                        "used": parts[2],
                        "avail": parts[3],
                        "use%": parts[4],
                        "mount": parts[5],
                    }
                )
        return disks

    def network_cmd(self):
        return "ip -4 addr show 2>/dev/null | grep -E 'inet ' || ipconfig 2>/dev/null"

    def who_cmd(self):
        return "who 2>/dev/null || query user 2>/dev/null"

    def log_paths(self):
        return ("/var/log/syslog", "/var/log/auth.log", "/var/log/messages")

    def python_package(self):
        return "python3"

    def nodejs_package(self):
        return "nodejs"

    def script_shell(self):
        return "bash"

    def md5_cmd(self, path):
        return f"md5sum {shlex.quote(path)} 2>/dev/null || echo none"


class LinuxProfile(OsProfile):
    key = "linux"
    family = "posix"


class WindowsProfile(OsProfile):
    key = "windows"
    family = "windows"

    def python_package(self):
        return "python"

    def nodejs_package(self):
        return "nodejs-lts"

    def cpu_cmd(self):
        return WINDOWS_CPU_CMD

    def ram_cmd(self):
        return WINDOWS_RAM_CMD

    def disk_cmd(self):
        return WINDOWS_DISK_CMD


class BsdProfile(OsProfile):
    """Shared command shapes for FreeBSD, OpenBSD and NetBSD.

    ``vmstat`` and ``df -kP`` are POSIX-familiar across the three systems;
    only the RAM ``sysctl`` names differ per OS, so subclasses override
    ``ram_cmd`` and inherit the parsers.
    """

    family = "posix"

    def cpu_cmd(self):
        return "vmstat 1 2"

    def parse_cpu(self, raw):
        try:
            lines = [line for line in (raw or "").splitlines() if line.strip()]
            idle = float(lines[-1].split()[-1])
        except (IndexError, ValueError):
            return None
        return round(100.0 - idle, 1)

    def disk_cmd(self):
        return "df -kP /"

    def parse_disk(self, raw):
        try:
            lines = [
                line
                for line in (raw or "").splitlines()
                if line.strip() and not line.lower().startswith("filesystem")
            ]
            parts = lines[-1].split()
            total_kb = int(parts[1])
            avail_kb = int(parts[3])
        except (IndexError, ValueError):
            return None
        total = total_kb / 1048576
        free = avail_kb / 1048576
        used = total - free
        pct = round((used / total) * 100, 1) if total > 0 else 0
        return {
            "total_gb": round(total, 1),
            "used_gb": round(used, 1),
            "free_gb": round(free, 1),
            "percent": pct,
        }

    def parse_ram(self, raw):
        try:
            values = [int(line) for line in (raw or "").splitlines() if line.strip()]
        except ValueError:
            return None
        if len(values) < 3:
            return None
        total_bytes, page_size, free_pages = values[0], values[1], values[2]
        inactive_pages = values[3] if len(values) > 3 else 0
        if total_bytes <= 0 or page_size <= 0:
            return None
        total = total_bytes / 1073741824
        free = (free_pages + inactive_pages) * page_size / 1073741824
        used = total - free
        pct = round((used / total) * 100, 1) if total > 0 else 0
        return {
            "total_gb": round(total, 1),
            "used_gb": round(used, 1),
            "free_gb": round(free, 1),
            "percent": pct,
        }

    def uptime_cmd(self):
        return "uptime"

    def top_cmd(self, sort_by, limit):
        return "ps -axo pid,pcpu,pmem,command"

    def parse_top(self, raw, sort_by, limit):
        column = 1 if sort_by == "cpu" else 2
        rows = []
        for line in (raw or "").splitlines():
            parts = line.split()
            if len(parts) < 4 or not parts[0].isdigit():
                continue
            rows.append((_as_float(parts[column]), parts[0], parts[column], " ".join(parts[3:])))
        rows.sort(key=lambda row: row[0], reverse=True)
        return [
            {"pid": pid, "usage": usage, "name": name}
            for _, pid, usage, name in rows[:limit]
        ]

    def disk_detail_cmd(self):
        return "df -h"

    def parse_disk_detail(self, raw):
        disks = []
        for line in (raw or "").splitlines():
            if line.startswith("Filesystem"):
                continue
            parts = line.split()
            if len(parts) < 6 or not parts[0].startswith("/"):
                continue
            disks.append(
                {
                    "device": parts[0],
                    "size": parts[1],
                    "used": parts[2],
                    "avail": parts[3],
                    "use%": parts[4],
                    "mount": parts[5],
                }
            )
        return disks

    def network_cmd(self):
        return "ifconfig -a"

    def who_cmd(self):
        return "who"

    def log_paths(self):
        return ("/var/log/messages", "/var/log/auth.log")

    def python_package(self):
        return "python3"

    def nodejs_package(self):
        return "node"

    def script_shell(self):
        return "sh"

    def md5_cmd(self, path):
        return f"md5 -q {shlex.quote(path)} 2>/dev/null || echo none"


class FreeBsdProfile(BsdProfile):
    key = "freebsd"

    def ram_cmd(self):
        return (
            "sysctl -n hw.physmem vm.stats.vm.v_page_size "
            "vm.stats.vm.v_free_count vm.stats.vm.v_inactive_count"
        )


class OpenBsdProfile(BsdProfile):
    key = "openbsd"

    def ram_cmd(self):
        return "sysctl -n hw.physmem hw.pagesize vm.uvmexp.free"

    def python_package(self):
        return "python%3"

    def log_paths(self):
        return ("/var/log/messages", "/var/log/authlog")


class NetBsdProfile(BsdProfile):
    key = "netbsd"

    def ram_cmd(self):
        return "sysctl -n hw.physmem64 hw.pagesize vm.uvmexp.free vm.uvmexp.inactive"

    def nodejs_package(self):
        return "nodejs"

    def log_paths(self):
        return ("/var/log/messages", "/var/log/authlog")


_PROFILES = {
    "linux": LinuxProfile(),
    "windows": WindowsProfile(),
    "freebsd": FreeBsdProfile(),
    "openbsd": OpenBsdProfile(),
    "netbsd": NetBsdProfile(),
}


def get_profile(os_type):
    """Return the profile for *os_type*; unknown values fall back to Linux."""
    value = (os_type or "linux").strip().lower()
    return _PROFILES.get(value, _PROFILES["linux"])
