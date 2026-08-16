import csv
import os
from datetime import datetime
from pathlib import Path


class HistoryManager:
    def __init__(self, resource_monitor, base_dir=None):
        self.monitor = resource_monitor
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        self.base_dir = Path(base_dir)
        self.history_dir = self.base_dir / "history"
        self.history_dir.mkdir(exist_ok=True)

    def record_snapshot(self, server_name, metrics):
        csv_file = self.history_dir / f"{server_name}.csv"
        file_exists = csv_file.exists()

        with open(csv_file, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "cpu_percent", "ram_total_gb", "ram_used_gb", "ram_percent", "disk_total_gb", "disk_used_gb", "disk_percent"])

            cpu = metrics.get("cpu_percent") or 0
            ram = metrics.get("ram") or {}
            disk = metrics.get("disk") or {}

            writer.writerow([
                datetime.now().isoformat(),
                cpu,
                ram.get("total_gb", 0),
                ram.get("used_gb", 0),
                ram.get("percent", 0),
                disk.get("total_gb", 0),
                disk.get("used_gb", 0),
                disk.get("percent", 0),
            ])

    def record_all_servers(self, server_names):
        for name in server_names:
            try:
                metrics = self.monitor.get_all_metrics(name)
                if metrics:
                    self.record_snapshot(name, metrics)
            except Exception:
                continue

    def get_history(self, server_name, limit=100):
        csv_file = self.history_dir / f"{server_name}.csv"
        if not csv_file.exists():
            return []

        rows = []
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        return rows[-limit:]

    def get_stats(self, server_name):
        history = self.get_history(server_name, limit=1000)
        if not history:
            return None

        cpus = [float(r["cpu_percent"]) for r in history if r["cpu_percent"]]
        rams = [float(r["ram_percent"]) for r in history if r["ram_percent"]]
        disks = [float(r["disk_percent"]) for r in history if r["disk_percent"]]

        return {
            "server": server_name,
            "samples": len(history),
            "cpu": {
                "avg": round(sum(cpus) / len(cpus), 1) if cpus else 0,
                "min": round(min(cpus), 1) if cpus else 0,
                "max": round(max(cpus), 1) if cpus else 0,
            },
            "ram": {
                "avg": round(sum(rams) / len(rams), 1) if rams else 0,
                "min": round(min(rams), 1) if rams else 0,
                "max": round(max(rams), 1) if rams else 0,
            },
            "disk": {
                "avg": round(sum(disks) / len(disks), 1) if disks else 0,
                "min": round(min(disks), 1) if disks else 0,
                "max": round(max(disks), 1) if disks else 0,
            },
        }

    def get_history_file(self, server_name):
        return self.history_dir / f"{server_name}.csv"

    def clear_history(self, server_name=None):
        if server_name:
            csv_file = self.history_dir / f"{server_name}.csv"
            if csv_file.exists():
                csv_file.unlink()
        else:
            for f in self.history_dir.glob("*.csv"):
                f.unlink()
