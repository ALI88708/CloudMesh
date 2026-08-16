import subprocess
import json
import os


class GPUTelemetry:
    """Read GPU metrics using nvidia-smi (works on Windows & Linux)."""

    NVIDIA_SMI_CMD = [
        "nvidia-smi",
        "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]

    def get_local_gpu(self):
        try:
            r = subprocess.run(
                self.NVIDIA_SMI_CMD,
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0:
                return None
            line = r.stdout.strip()
            if not line:
                return None
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 5:
                return None
            return {
                "name": parts[0],
                "utilization_percent": float(parts[1]),
                "memory_used_mb": float(parts[2]),
                "memory_total_mb": float(parts[3]),
                "memory_free_mb": round(float(parts[3]) - float(parts[2]), 1),
                "temperature_c": float(parts[4]),
            }
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, IndexError):
            return None

    def get_remote_gpu(self, server_mgr, server_name):
        cmd = "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits 2>/dev/null"
        try:
            result = server_mgr.execute(server_name, cmd)
            if result["exit_code"] != 0:
                return None
            line = result["stdout"].strip()
            if not line:
                return None
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 5:
                return None
            return {
                "name": parts[0],
                "utilization_percent": float(parts[1]),
                "memory_used_mb": float(parts[2]),
                "memory_total_mb": float(parts[3]),
                "memory_free_mb": round(float(parts[3]) - float(parts[2]), 1),
                "temperature_c": float(parts[4]),
            }
        except Exception:
            return None

    def get_all_gpus(self, server_mgr, server_name):
        cmd = "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits 2>/dev/null"
        try:
            result = server_mgr.execute(server_name, cmd)
            if result["exit_code"] != 0:
                return []
            gpus = []
            for line in result["stdout"].strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 5:
                    continue
                gpus.append({
                    "name": parts[0],
                    "utilization_percent": float(parts[1]),
                    "memory_used_mb": float(parts[2]),
                    "memory_total_mb": float(parts[3]),
                    "memory_free_mb": round(float(parts[3]) - float(parts[2]), 1),
                    "temperature_c": float(parts[4]),
                })
            return gpus
        except Exception:
            return []

    def calculate_gpu_weight(self, gpu_data):
        if gpu_data is None:
            return 0
        util = gpu_data.get("utilization_percent", 100)
        mem_free = gpu_data.get("memory_free_mb", 0)
        util_free = 100 - util
        mem_score = min(mem_free / 10, 50)
        return round(util_free * 0.6 + mem_score * 0.4, 1)
