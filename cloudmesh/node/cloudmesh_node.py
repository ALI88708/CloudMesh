#!/usr/bin/env python3
"""CloudMesh Node - Agent with GPU telemetry, async jobs, SPA and tripwire."""

import hashlib
import hmac as hmac_mod
import json
import os
import platform
import secrets
import signal
import socket
import struct
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
TRIPWIRE_KEYS_FILE = BASE_DIR / ".tripwire_keys.json"
DEFAULT_PORT = 9999
DEFAULT_SPA_PORT = 9998
DEFAULT_SPA_WINDOW = 5
SPA_TIMESTAMP_MAX_AGE = 30


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


def _load_tripwire_keys():
    if TRIPWIRE_KEYS_FILE.exists():
        try:
            return json.loads(TRIPWIRE_KEYS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _log_tripwire_breach(key_used, source_ip):
    log_file = BASE_DIR / ".tripwire_log.json"
    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text())
        except Exception:
            entries = []
    entries.append({
        "event": "triggered",
        "timestamp": datetime.now().isoformat(),
        "source_ip": source_ip,
        "key_hash": hashlib.sha256(key_used.encode()).hexdigest()[:16],
    })
    entries = entries[-200:]
    log_file.write_text(json.dumps(entries, indent=2))


def _check_tripwire(key_used):
    tripwires = _load_tripwire_keys()
    for name, info in tripwires.items():
        if info.get("key") == key_used:
            return True, name
    return False, None


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
        allowed = (BASE_DIR / "data").resolve()
        allowed.mkdir(parents=True, exist_ok=True)
        resolved = Path(user_path).resolve()
        try:
            resolved.relative_to(allowed)
        except ValueError:
            return None
        real_allowed = allowed
        if os.name != "nt":
            real_allowed = Path(os.path.realpath(str(allowed)))
            real_resolved = Path(os.path.realpath(str(resolved)))
            if not str(real_resolved).startswith(str(real_allowed) + os.sep) and str(real_resolved) != str(real_allowed):
                return None
        return resolved
    except Exception:
        return None


class SpacListener:
    def __init__(self, auth_key, spa_port, tcp_port, window, on_open_callback):
        self.auth_key = auth_key
        self.spa_port = spa_port
        self.tcp_port = tcp_port
        self.window = window
        self.on_open = on_open_callback
        self._running = False
        self._used_nonces = set()
        self._nonce_lock = threading.Lock()
        self._sock = None

    def _validate_packet(self, packet_bytes, source_ip):
        try:
            packet = json.loads(packet_bytes.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False

        timestamp = packet.get("timestamp", 0)
        nonce = packet.get("nonce", "")
        signature = packet.get("hmac", "")

        if not timestamp or not nonce or not signature:
            return False

        now = time.time()
        if abs(now - timestamp) > SPA_TIMESTAMP_MAX_AGE:
            _log(f"SPA: Rejected stale packet from {source_ip} (age={abs(now - timestamp):.1f}s)")
            return False

        with self._nonce_lock:
            if nonce in self._used_nonces:
                _log(f"SPA: Rejected replay nonce from {source_ip}")
                return False
            self._used_nonces.add(nonce)
            if len(self._used_nonces) > 10000:
                self._used_nonces = set(list(self._used_nonces)[-5000:])

        msg = f"{timestamp}:{nonce}"
        expected_hmac = hmac_mod.new(
            self.auth_key.encode(), msg.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac_mod.compare_digest(expected_hmac, signature):
            _log(f"SPA: Invalid HMAC from {source_ip}")
            return False

        return True

    def _listen_loop(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.settimeout(1.0)
        try:
            self._sock.bind(("0.0.0.0", self.spa_port))
        except OSError as e:
            _log(f"SPA: Failed to bind UDP port {self.spa_port}: {e}")
            return
        _log(f"SPA: UDP listener started on port {self.spa_port}")

        while self._running:
            try:
                data, addr = self._sock.recvfrom(1024)
                source_ip = addr[0]
                if self._validate_packet(data, source_ip):
                    _log(f"SPA: Valid knock from {source_ip} — opening TCP {self.tcp_port} for {self.window}s")
                    self.on_open(self.window, source_ip)
            except socket.timeout:
                continue
            except Exception as e:
                _log(f"SPA: Error: {e}")

        try:
            self._sock.close()
        except Exception:
            pass

    def start(self):
        self._running = True
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self._running = False


class NodeAgent:
    def __init__(self, port=DEFAULT_PORT, auth_key=None, bind_host="0.0.0.0",
                 tls_cert=None, tls_key=None,
                 spa=False, spa_port=DEFAULT_SPA_PORT, spa_window=DEFAULT_SPA_WINDOW):
        self.port = port
        self.auth_key = auth_key or get_or_create_key()
        self.bind_host = bind_host
        self.tls_cert = tls_cert
        self.tls_key = tls_key
        self._running = False
        self._jobs = {}
        self._lock = threading.Lock()
        self._load_jobs()

        self.spa_mode = spa
        self.spa_port = spa_port
        self.spa_window = spa_window
        self._spa_open = False
        self._spa_lock = threading.Lock()
        self._spa_event = threading.Event()

        from core.ddos import DDoSProtection
        self._ddos = DDoSProtection()
        self._spac = None

    def _on_spa_knock(self, window, source_ip):
        with self._spa_lock:
            self._spa_open = True
            self._spa_event.set()

        port = self.port
        try:
            subprocess.run(
                ["iptables", "-I", "INPUT", "-p", "tcp", "--dport", str(port),
                 "-s", source_ip, "-j", "ACCEPT"],
                capture_output=True, timeout=5
            )
            _log(f"SPA: iptables ACCEPT rule added for TCP {port} from {source_ip}")
        except Exception as e:
            _log(f"SPA: iptables failed: {e}")

        def close_after_delay():
            time.sleep(window)
            try:
                subprocess.run(
                    ["iptables", "-D", "INPUT", "-p", "tcp", "--dport", str(port),
                     "-s", source_ip, "-j", "ACCEPT"],
                    capture_output=True, timeout=5
                )
                _log(f"SPA: iptables ACCEPT rule removed for TCP {port} from {source_ip}")
            except Exception as e:
                _log(f"SPA: iptables cleanup failed: {e}")
            with self._spa_lock:
                self._spa_open = False
                self._spa_event.clear()
            _log(f"SPA: TCP port {port} closed after {window}s window")

        threading.Thread(target=close_after_delay, daemon=True).start()

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
        ip = addr[0]
        try:
            allowed, reason = self._ddos.check_connection(ip)
            if not allowed:
                _log(f"DDoS: Rejected {ip}: {reason}")
                self._send_msg(client, {"type": "error", "message": "Rejected"})
                return

            req = self._recv_msg(client)
            if req is None:
                return

            auth_key = req.get("auth", "") or ""
            if not hmac_mod.compare_digest(auth_key, self.auth_key):
                is_banned = self._ddos.on_auth_failure(ip)
                is_tripwire, tripwire_name = _check_tripwire(auth_key)
                if is_tripwire:
                    _log(f"TRIPWIRE TRIGGERED! Key '{tripwire_name}' used from {ip}")
                    _log_tripwire_breach(auth_key, ip)
                if is_banned:
                    _log(f"DDoS: IP {ip} banned after repeated auth failures")
                self._send_msg(client, {"type": "error", "message": "Auth failed"})
                return

            self._ddos.on_auth_success(ip)

            action = req.get("action", "")
            if action == "ping":
                resp = {"type": "pong", "time": datetime.now().isoformat()}
            elif action == "info":
                resp = {"type": "info", "data": {
                    "hostname": socket.gethostname(),
                    "platform": sys.platform,
                    "arch": platform.machine(),
                    "python": platform.python_version(),
                    "spa_mode": self.spa_mode,
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
            elif action == "rotate_key":
                new_key = req.get("new_key", "")
                if not new_key or len(new_key) < 32:
                    resp = {"type": "rotate_key", "data": {"success": False, "message": "Invalid new key"}}
                else:
                    KEY_FILE.write_text(new_key)
                    self.auth_key = new_key
                    _log("Auth key rotated via authenticated rotate_key request")
                    resp = {"type": "rotate_key", "data": {"success": True}}
            else:
                resp = {"type": "error", "message": f"Unknown: {action}"}
            self._send_msg(client, resp)
        except Exception as e:
            try:
                self._send_msg(client, {"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            self._ddos.release_connection(ip)
            try:
                client.close()
            except Exception:
                pass

    def serve(self):
        self._running = True
        PID_FILE.write_text(str(os.getpid()))

        if self.spa_mode:
            self._spac = SpacListener(
                auth_key=self.auth_key,
                spa_port=self.spa_port,
                tcp_port=self.port,
                window=self.spa_window,
                on_open_callback=self._on_spa_knock,
            )
            self._spac.start()

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.bind_host, self.port))
        srv.listen(16)
        srv.settimeout(1)

        if self.tls_cert and self.tls_key:
            import ssl
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(self.tls_cert, self.tls_key)
            srv = ctx.wrap_socket(srv, server_side=True)
            _log("TLS enabled")

        mode_str = f"SPA(UDP:{self.spa_port})" if self.spa_mode else "TCP"
        _log(f"Node started on {self.bind_host}:{self.port} [{mode_str}]")

        if not self.tls_cert or not self.tls_key:
            _log("WARNING: TLS disabled — traffic is unencrypted. Use --tls-cert/--tls-key for production.")
        if not self.spa_mode:
            _log("WARNING: SPA disabled — TCP port is visible to scanners. Use --spa for production.")

        if self.spa_mode and platform.system() != "Windows":
            result = subprocess.run(
                ["iptables", "-A", "INPUT", "-p", "tcp", "--dport", str(self.port), "-j", "DROP"],
                capture_output=True, timeout=5
            )
            if result.returncode != 0:
                _log("FATAL: SPA mode requested but iptables DROP rule failed — refusing to start exposed")
                return
            _log(f"SPA: iptables DROP rule added for TCP {self.port}")

        if platform.system() != "Windows":
            signal.signal(signal.SIGTERM, lambda s, f: setattr(self, "_running", False))

        while self._running:
            try:
                if self.spa_mode:
                    with self._spa_lock:
                        spa_open = self._spa_open
                    if not spa_open:
                        time.sleep(0.1)
                        continue

                c, a = srv.accept()
                threading.Thread(target=self._handle, args=(c, a), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                pass

        if self._spac:
            self._spac.stop()
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


def cmd_start(port=DEFAULT_PORT, bind_host="0.0.0.0", tls_cert=None, tls_key=None,
              spa=False, spa_port=DEFAULT_SPA_PORT, spa_window=DEFAULT_SPA_WINDOW):
    existing = _read_pid()
    if existing and _is_running(existing):
        print(f"Already running (PID {existing})")
        return
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    agent = NodeAgent(port=port, bind_host=bind_host, tls_cert=tls_cert, tls_key=tls_key,
                      spa=spa, spa_port=spa_port, spa_window=spa_window)
    mode_str = f"SPA(UDP:{spa_port}, window:{spa_window}s)" if spa else "TCP"
    print(f"Starting node agent on {bind_host}:{port} [{mode_str}]...")
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
    start_p.add_argument("--bind", "-b", default="0.0.0.0")
    start_p.add_argument("--tls-cert", default=None)
    start_p.add_argument("--tls-key", default=None)
    start_p.add_argument("--spa", action="store_true",
                         help="Enable SPA (Single Packet Authorization) — TCP port invisible to scanners")
    start_p.add_argument("--spa-port", type=int, default=DEFAULT_SPA_PORT,
                         help="UDP port for SPA knocks (default: 9998)")
    start_p.add_argument("--spa-window", type=int, default=DEFAULT_SPA_WINDOW,
                         help="Seconds TCP port stays open after knock (default: 5)")
    sub.add_parser("stop")
    sub.add_parser("status")
    args = p.parse_args()
    if args.command == "start":
        cmd_start(port=args.port, bind_host=args.bind, tls_cert=args.tls_cert, tls_key=args.tls_key,
                  spa=args.spa, spa_port=args.spa_port, spa_window=args.spa_window)
    elif args.command == "stop":
        cmd_stop()
    elif args.command == "status":
        cmd_status()
    else:
        p.print_help()


if __name__ == "__main__":
    main()
