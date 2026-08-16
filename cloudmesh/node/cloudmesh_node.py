#!/usr/bin/env python3
"""CloudMesh Node - Agent with GPU telemetry and async jobs."""

import hashlib
import hmac as hmac_mod
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

BASE_DIR = Path(__file__).resolve().parent
KEY_FILE = BASE_DIR / ".node_key"
JOBS_DIR = BASE_DIR / "jobs"
PID_FILE = BASE_DIR / "cloudmesh_node.pid"
LOG_FILE = BASE_DIR / "cloudmesh_node.log"
DEFAULT_PORT = 9999


def get_or_create_key():
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    key = uuid.uuid4().hex[:32]
    KEY_FILE.write_text(key)
    try:
        KEY_FILE.chmod(0o600)
    except Exception:
        pass
    return key


def _log(msg):
    ts = datetime.now().isoformat()
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def get_gpu_info():
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        line = result.stdout.strip()
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


def get_metrics():
    metrics = {}
    if HAS_PSUTIL:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk_path = "C:\\" if os.name == "nt" else "/"
        disk = psutil.disk_usage(disk_path)
        metrics = {
            "cpu_percent": cpu,
            "ram": {
                "total_gb": round(ram.total / 1024**3, 1),
                "used_gb": round(ram.used / 1024**3, 1),
                "free_gb": round(ram.available / 1024**3, 1),
                "percent": ram.percent,
            },
            "disk": {
                "total_gb": round(disk.total / 1024**3, 1),
                "used_gb": round(disk.used / 1024**3, 1),
                "free_gb": round(disk.free / 1024**3, 1),
                "percent": disk.percent,
            },
        }
    else:
        try:
            with open("/proc/stat") as f:
                parts = f.readline().split()[1:]
            t1, i1 = sum(int(x) for x in parts), int(parts[3])
            time.sleep(0.5)
            with open("/proc/stat") as f:
                parts = f.readline().split()[1:]
            t2, i2 = sum(int(x) for x in parts), int(parts[3])
            total = t2 - t1
            idle = i2 - i1
            cpu = round((1 - idle / total) * 100, 1) if total > 0 else 0
        except Exception:
            cpu = 0
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            info = {l.split()[0].rstrip(":"): int(l.split()[1]) for l in lines}
            rt = info["MemTotal"] / 1048576
            rf = info["MemAvailable"] / 1048576
            ru = rt - rf
            rp = round(ru / rt * 100, 1) if rt > 0 else 0
        except Exception:
            rt = rf = ru = rp = 0
        try:
            st = os.statvfs("/")
            dt = (st.f_blocks * st.f_frsize) / (1024**3)
            df_ = (st.f_bavail * st.f_frsize) / (1024**3)
            du = dt - df_
            dp = round(du / dt * 100, 1) if dt > 0 else 0
        except Exception:
            dt = df_ = du = dp = 0
        metrics = {
            "cpu_percent": cpu,
            "ram": {"total_gb": round(rt, 1), "used_gb": round(ru, 1), "free_gb": round(rf, 1), "percent": rp},
            "disk": {"total_gb": round(dt, 1), "used_gb": round(du, 1), "free_gb": round(df_, 1), "percent": dp},
        }

    gpu = get_gpu_info()
    metrics["gpu"] = gpu
    return metrics


def _safe_path(user_path):
    try:
        resolved = Path(user_path).resolve()
        if ".." in user_path.split("/") or ".." in user_path.split("\\"):
            return None
        allowed = BASE_DIR / "data"
        allowed.mkdir(parents=True, exist_ok=True)
        if not str(resolved).startswith(str(allowed.resolve())):
            return None
        return resolved
    except Exception:
        return None


class NodeAgent:
    def __init__(self, port=DEFAULT_PORT, auth_key=None):
        self.port = port
        self.auth_key = auth_key or get_or_create_key()
        self._running = False
        self._jobs = {}
        self._lock = threading.Lock()
        self._load_jobs()

    def _load_jobs(self):
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        for f in JOBS_DIR.glob("*.json"):
            try:
                job = json.loads(f.read_text())
                self._jobs[job["id"]] = job
            except Exception:
                pass

    def _save_job(self, job):
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        path = JOBS_DIR / f"{job['id']}.json"
        path.write_text(json.dumps(job, indent=2))

    def _recv_msg(self, sock):
        header = b""
        while len(header) < 4:
            chunk = sock.recv(4 - len(header))
            if not chunk:
                return None
            header += chunk
        length = int.from_bytes(header, "big")
        if length > 50 * 1024 * 1024:
            return None
        data = b""
        while len(data) < length:
            chunk = sock.recv(min(length - len(data), 65536))
            if not chunk:
                break
            data += chunk
        return json.loads(data.decode())

    def _send_msg(self, sock, resp):
        msg = json.dumps(resp).encode()
        sock.sendall(len(msg).to_bytes(4, "big") + msg)

    def _handle_execute(self, cmd, timeout=300):
        try:
            kwargs = {"shell": True, "capture_output": True, "text": True, "timeout": timeout}
            result = subprocess.run(cmd, **kwargs)
            return {"success": result.returncode == 0, "exit_code": result.returncode,
                    "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "exit_code": -1, "stdout": "", "stderr": "Timeout"}
        except Exception as e:
            return {"success": False, "exit_code": -1, "stdout": "", "stderr": str(e)}

    def _handle_start_job(self, cmd, timeout=300):
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id, "command": cmd, "status": "running",
            "started_at": datetime.now().isoformat(), "finished_at": None,
            "exit_code": None, "stdout": "", "stderr": "", "timeout": timeout,
        }
        with self._lock:
            self._jobs[job_id] = job
        self._save_job(job)
        _log(f"Job {job_id} started: {cmd}")

        def run():
            try:
                kwargs = {"shell": True, "capture_output": True, "text": True, "timeout": timeout}
                r = subprocess.run(cmd, **kwargs)
                job["exit_code"] = r.returncode
                job["stdout"] = r.stdout
                job["stderr"] = r.stderr
                job["status"] = "completed" if r.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                job["status"] = "failed"
                job["stderr"] = "Timeout"
                job["exit_code"] = -1
            except Exception as e:
                job["status"] = "failed"
                job["stderr"] = str(e)
                job["exit_code"] = -1
            finally:
                job["finished_at"] = datetime.now().isoformat()
                self._save_job(job)
                _log(f"Job {job_id} finished: {job['status']}")

        threading.Thread(target=run, daemon=True).start()
        return {"job_id": job_id, "status": "running"}

    def _handle_check_job(self, job_id):
        with self._lock:
            return self._jobs.get(job_id, {"error": "Job not found"})

    def _handle_list_jobs(self):
        with self._lock:
            return list(self._jobs.values())

    def _handle_kill_job(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            return {"error": "Job not found"}
        if job["status"] == "running":
            job["status"] = "cancelled"
            job["finished_at"] = datetime.now().isoformat()
            self._save_job(job)
            return {"success": True, "message": f"Job {job_id} cancelled"}
        return {"success": False, "message": f"Job status: {job['status']}"}

    def _handle(self, client, addr):
        try:
            req = self._recv_msg(client)
            if req is None:
                return
            if not hmac_mod.compare_digest(req.get("auth", "") or "", self.auth_key):
                self._send_msg(client, {"type": "error", "message": "Auth failed"})
                return
            action = req.get("action", "")
            if action == "ping":
                resp = {"type": "pong", "time": datetime.now().isoformat()}
            elif action == "info":
                resp = {"type": "info", "data": {
                    "hostname": socket.gethostname(),
                    "platform": sys.platform,
                    "arch": platform.machine(),
                    "python": platform.python_version(),
                }}
            elif action == "metrics":
                resp = {"type": "metrics", "data": get_metrics()}
            elif action == "gpu":
                resp = {"type": "gpu", "data": get_gpu_info()}
            elif action == "execute":
                _log(f"Exec: {req.get('command', '')}")
                resp = {"type": "execute", "data": self._handle_execute(
                    req.get("command", ""), req.get("timeout", 300))}
            elif action == "start_job":
                resp = {"type": "start_job", "data": self._handle_start_job(
                    req.get("command", ""), req.get("timeout", 300))}
            elif action == "check_job":
                resp = {"type": "check_job", "data": self._handle_check_job(
                    req.get("job_id", ""))}
            elif action == "list_jobs":
                resp = {"type": "list_jobs", "data": self._handle_list_jobs()}
            elif action == "kill_job":
                resp = {"type": "kill_job", "data": self._handle_kill_job(
                    req.get("job_id", ""))}
            elif action == "upload":
                path = req.get("data", {}).get("path", "")
                safe = _safe_path(path)
                if safe is None:
                    resp = {"type": "upload", "data": {"success": False, "message": "Access denied"}}
                else:
                    try:
                        safe.parent.mkdir(parents=True, exist_ok=True)
                        with open(safe, req.get("data", {}).get("mode", "w")) as f:
                            f.write(req.get("data", {}).get("content", ""))
                        resp = {"type": "upload", "data": {"success": True, "message": f"Written to {safe}"}}
                    except Exception as e:
                        resp = {"type": "upload", "data": {"success": False, "message": str(e)}}
            elif action == "download":
                path = req.get("data", {}).get("path", "")
                safe = _safe_path(path)
                if safe is None:
                    resp = {"type": "download", "data": {"success": False, "message": "Access denied"}}
                elif not safe.exists():
                    resp = {"type": "download", "data": {"success": False, "message": "File not found"}}
                else:
                    try:
                        with open(safe, "r") as f:
                            content = f.read()
                        resp = {"type": "download", "data": {"success": True, "content": content, "size": len(content)}}
                    except Exception as e:
                        resp = {"type": "download", "data": {"success": False, "message": str(e)}}
            else:
                resp = {"type": "error", "message": f"Unknown: {action}"}
            self._send_msg(client, resp)
        except Exception as e:
            try:
                self._send_msg(client, {"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            try:
                client.close()
            except Exception:
                pass

    def serve(self):
        self._running = True
        PID_FILE.write_text(str(os.getpid()))
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", self.port))
        srv.listen(16)
        srv.settimeout(1)
        _log(f"Node started on port {self.port}")
        if platform.system() != "Windows":
            signal.signal(signal.SIGTERM, lambda s, f: setattr(self, "_running", False))
        while self._running:
            try:
                c, a = srv.accept()
                threading.Thread(target=self._handle, args=(c, a), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                pass
        srv.close()
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass


def _read_pid():
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except Exception:
            pass
    return None


def _is_running(pid):
    if pid is None:
        return False
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x0400, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def cmd_start(port=DEFAULT_PORT):
    existing = _read_pid()
    if existing and _is_running(existing):
        print(f"Already running (PID {existing})")
        return
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    agent = NodeAgent(port=port)
    print(f"Starting node agent on port {port}...")
    try:
        agent.serve()
    except KeyboardInterrupt:
        pass


def cmd_stop():
    pid = _read_pid()
    if not pid:
        print("Not running")
        return
    if not _is_running(pid):
        print(f"PID {pid} not running, cleaning up")
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return
    if platform.system() == "Windows":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        os.kill(pid, signal.SIGTERM)
    print(f"Stopped (PID {pid})")
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def cmd_status():
    pid = _read_pid()
    if not pid:
        print("STOPPED")
    elif _is_running(pid):
        print(f"RUNNING (PID {pid})")
    else:
        print("STOPPED (stale PID)")
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass


def main():
    import argparse
    p = argparse.ArgumentParser(description="CloudMesh Node")
    sub = p.add_subparsers(dest="command")
    start_p = sub.add_parser("start")
    start_p.add_argument("--port", "-p", type=int, default=DEFAULT_PORT)
    sub.add_parser("stop")
    sub.add_parser("status")
    args = p.parse_args()
    if args.command == "start":
        cmd_start(port=args.port)
    elif args.command == "stop":
        cmd_stop()
    elif args.command == "status":
        cmd_status()
    else:
        p.print_help()


if __name__ == "__main__":
    main()
