import os
import psutil

from .gpu import GPUTelemetry
from .osprofile import get_profile


class ResourceMonitor:
    def __init__(self, server_manager):
        self.server_mgr = server_manager
        self._cache = {}
        self.gpu_telemetry = GPUTelemetry()

    def _run_cmd(self, server_name, cmd):
        result = self.server_mgr.execute(server_name, cmd)
        if result["exit_code"] != 0:
            return None
        return result["stdout"].strip()

    def _profile(self, server_name):
        info = self.server_mgr.get_server_info(server_name)
        return get_profile(info.get("os_type"))

    def get_cpu(self, server_name):
        profile = self._profile(server_name)
        raw = self._run_cmd(server_name, profile.cpu_cmd())
        if raw is None:
            return None
        return profile.parse_cpu(raw)

    def get_ram(self, server_name):
        profile = self._profile(server_name)
        raw = self._run_cmd(server_name, profile.ram_cmd())
        if raw is None:
            return None
        return profile.parse_ram(raw)

    def get_disk(self, server_name):
        profile = self._profile(server_name)
        raw = self._run_cmd(server_name, profile.disk_cmd())
        if raw is None:
            return None
        return profile.parse_disk(raw)

    def get_all_metrics(self, server_name):
        cpu = self.get_cpu(server_name)
        ram = self.get_ram(server_name)
        disk = self.get_disk(server_name)
        gpu = self.get_gpu(server_name)
        metrics = {
            "cpu_percent": cpu,
            "ram": ram,
            "disk": disk,
            "gpu": gpu,
        }
        self._cache[server_name] = metrics
        return metrics

    def get_gpu(self, server_name):
        try:
            return self.gpu_telemetry.get_remote_gpu(self.server_mgr, server_name)
        except Exception:
            return None

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
