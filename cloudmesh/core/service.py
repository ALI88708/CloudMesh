import json
import os
import time
import signal
import sys
from datetime import datetime
from pathlib import Path


class ServiceMode:
    def __init__(self, server_manager, resource_monitor, alert_manager, history_manager):
        self.server_mgr = server_manager
        self.monitor = resource_monitor
        self.alerts = alert_manager
        self.history = history_manager
        self._running = False
        self.pid_file = Path(__file__).parent.parent / "service.pid"
        self.log_file = Path(__file__).parent.parent / "service.log"

    def _log(self, message):
        timestamp = datetime.now().isoformat()
        line = f"[{timestamp}] {message}\n"
        try:
            with open(self.log_file, "a") as f:
                f.write(line)
        except Exception:
            pass

    def start(self, interval=60):
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text().strip())
                os.kill(pid, 0)
                print(f"Service already running (PID: {pid})")
                return
            except (ValueError, ProcessLookupError, PermissionError):
                self.pid_file.unlink()

        self.pid_file.write_text(str(os.getpid()))
        self._running = True
        self._log("Service started")

        def handler(sig, frame):
            self._running = False
            self._log("Service stopping...")

        signal.signal(signal.SIGINT, handler)
        if os.name != "nt":
            signal.signal(signal.SIGTERM, handler)

        try:
            while self._running:
                self._check_cycle()
                time.sleep(interval)
        finally:
            self.pid_file.unlink(missing_ok=True)
            self._log("Service stopped")

    def _check_cycle(self):
        try:
            for name in self.server_mgr.list_servers():
                try:
                    metrics = self.monitor.get_all_metrics(name)
                    if metrics:
                        self.history.record_snapshot(name, metrics)
                except Exception:
                    continue

            triggered = self.alerts.check_alerts()
            if triggered:
                for a in triggered:
                    self._log(f"ALERT: {a['rule']} on {a['server']} - {a['metric']}={a['value']}%")
        except Exception as e:
            self._log(f"Error in check cycle: {e}")

    def stop(self):
        if not self.pid_file.exists():
            print("Service not running")
            return
        try:
            pid = int(self.pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            self.pid_file.unlink(missing_ok=True)
            print(f"Service stopped (PID: {pid})")
        except (ValueError, ProcessLookupError):
            self.pid_file.unlink(missing_ok=True)
            print("Service stopped")
        except Exception as e:
            print(f"Error stopping service: {e}")
            self.pid_file.unlink(missing_ok=True)

    def status(self):
        if not self.pid_file.exists():
            print("Service: STOPPED")
            return False
        try:
            pid = int(self.pid_file.read_text().strip())
            os.kill(pid, 0)
            print(f"Service: RUNNING (PID: {pid})")
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            self.pid_file.unlink(missing_ok=True)
            print("Service: STOPPED (stale PID)")
            return False

    def logs(self, limit=20):
        if not self.log_file.exists():
            print("No logs found")
            return
        lines = self.log_file.read_text().strip().split("\n")
        for line in lines[-limit:]:
            print(line)
