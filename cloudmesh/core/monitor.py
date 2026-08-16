import json
import os
import psutil


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


class ResourceMonitor:
    def __init__(self, server_manager):
        self.server_mgr = server_manager
        self._cache = {}

    def _run_cmd(self, server_name, cmd):
        result = self.server_mgr.execute(server_name, cmd)
        if result["exit_code"] != 0:
            return None
        return result["stdout"].strip()

    def get_cpu(self, server_name):
        info = self.server_mgr.get_server_info(server_name)
        os_type = info.get("os_type", "linux")
        cmd = WINDOWS_CPU_CMD if os_type == "windows" else LINUX_CPU_CMD
        raw = self._run_cmd(server_name, cmd)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def get_ram(self, server_name):
        info = self.server_mgr.get_server_info(server_name)
        os_type = info.get("os_type", "linux")
        cmd = WINDOWS_RAM_CMD if os_type == "windows" else LINUX_RAM_CMD
        raw = self._run_cmd(server_name, cmd)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def get_disk(self, server_name):
        info = self.server_mgr.get_server_info(server_name)
        os_type = info.get("os_type", "linux")
        cmd = WINDOWS_DISK_CMD if os_type == "windows" else LINUX_DISK_CMD
        raw = self._run_cmd(server_name, cmd)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def get_all_metrics(self, server_name):
        cpu = self.get_cpu(server_name)
        ram = self.get_ram(server_name)
        disk = self.get_disk(server_name)
        metrics = {
            "cpu_percent": cpu,
            "ram": ram,
            "disk": disk,
        }
        self._cache[server_name] = metrics
        return metrics

    def get_local_metrics(self):
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk_path = "C:\\" if os.name == "nt" else "/"
        disk = psutil.disk_usage(disk_path)
        return {
            "cpu_percent": cpu,
            "ram": {
                "total_gb": round(ram.total / (1024**3), 1),
                "used_gb": round(ram.used / (1024**3), 1),
                "free_gb": round(ram.available / (1024**3), 1),
                "percent": ram.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 1),
                "used_gb": round(disk.used / (1024**3), 1),
                "free_gb": round(disk.free / (1024**3), 1),
                "percent": disk.percent,
            },
        }

    def calculate_weight(self, metrics):
        if metrics is None:
            return 0
        cpu_free = 100 - (metrics.get("cpu_percent") or 100)
        ram = metrics.get("ram") or {}
        ram_free = ram.get("free_gb", 0)
        disk = metrics.get("disk") or {}
        disk_free = disk.get("free_gb", 0)

        cpu_w = cpu_free * 0.5
        ram_w = min(ram_free * 2, 50) * 0.3
        disk_w = min(disk_free * 0.5, 25) * 0.2
        return round(cpu_w + ram_w + disk_w, 1)

    def get_best_server(self, server_names):
        best_name = None
        best_weight = -1
        for name in server_names:
            try:
                metrics = self.get_all_metrics(name)
                weight = self.calculate_weight(metrics)
                if weight > best_weight:
                    best_weight = weight
                    best_name = name
            except Exception:
                continue
        return best_name, best_weight

    def get_all_servers_metrics(self):
        results = {}
        for name in self.server_mgr.list_servers():
            try:
                metrics = self.get_all_metrics(name)
                weight = self.calculate_weight(metrics)
                status = self.server_mgr.get_server_info(name).get("status", "unknown")
                results[name] = {
                    "metrics": metrics,
                    "weight": weight,
                    "status": status,
                }
            except Exception as e:
                results[name] = {
                    "metrics": None,
                    "weight": 0,
                    "status": f"error: {e}",
                }
        return results
