#!/usr/bin/env python3
"""CloudMesh Node - Agent with GPU telemetry, async jobs, SPA and tripwire."""

import hashlib
import hmac as hmac_mod
import json
import os
import platform
import random
import re
import secrets
import signal
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from . import cloudmesh_relay
except ImportError:  # standalone deployment: the relay module sits next to this file
    import cloudmesh_relay

BASE_DIR = Path(__file__).resolve().parent
KEY_FILE = BASE_DIR / ".node_key"
JOBS_DIR = BASE_DIR / "jobs"
PID_FILE = BASE_DIR / "cloudmesh_node.pid"
LOG_FILE = BASE_DIR / "cloudmesh_node.log"
TRIPWIRE_KEYS_FILE = BASE_DIR / ".tripwire_keys.json"
NODE_ID_FILE = BASE_DIR / ".node_id"
RELAY_CONFIG_FILE = BASE_DIR / ".node_relay.json"
DEFAULT_PORT = 9999
DEFAULT_SPA_PORT = 9998
DEFAULT_SPA_WINDOW = 5
SPA_TIMESTAMP_MAX_AGE = 30
METRICS_CACHE_SECONDS = 2.0
RELAY_PARKED_READ_TIMEOUT = 35.0
RELAY_BACKOFF_INITIAL = 1.0
RELAY_BACKOFF_MAX = 60.0
RELAY_HEX32 = re.compile(r"^[0-9a-f]{32}$")
RELAY_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_METRICS_CACHE = None
_METRICS_CACHE_AT = 0.0
_METRICS_LOCK = threading.Lock()

_BSD_OS_TYPES = ("freebsd", "openbsd", "netbsd")

_OS_TYPE_NAMES = {
    "linux": "linux",
    "windows": "windows",
    "freebsd": "freebsd",
    "openbsd": "openbsd",
    "netbsd": "netbsd",
}


def _system_os_type():
    """Map the running platform to one of the supported os_type keys."""
    return _OS_TYPE_NAMES.get(platform.system().lower(), "linux")


def _resolve_written_path(fd, safe_path):
    """Resolve a written file descriptor without assuming /proc exists."""
    proc_path = Path(f"/proc/self/fd/{fd}")
    if proc_path.exists():
        return Path(os.path.realpath(str(proc_path)))
    return Path(os.path.realpath(str(safe_path)))


def _spa_guard(system_name):
    """Return the fatal message when SPA cannot be guarded, else None."""
    if system_name.lower() == "linux":
        return None
    return (
        f"FATAL: SPA mode is not supported on {system_name} — the iptables port-knocking "
        "guard is Linux-only. Refusing to start with an exposed TCP port."
    )


def get_or_create_key():
    if KEY_FILE.exists():
        if os.name != "nt":
            KEY_FILE.chmod(0o600)
        return KEY_FILE.read_text().strip()
    key = secrets.token_hex(32)
    _write_auth_key(key)
    return key


def get_node_id():
    if not NODE_ID_FILE.exists():
        node_id = uuid.uuid4().hex
        try:
            descriptor = os.open(
                NODE_ID_FILE,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "w") as key_file:
                key_file.write(node_id)
    if os.name != "nt":
        NODE_ID_FILE.chmod(0o600)
    node_id = NODE_ID_FILE.read_text(encoding="utf-8").strip()
    if not node_id or len(node_id) != 32:
        raise RuntimeError(f"Invalid node identity file: {NODE_ID_FILE}")
    return node_id


def _write_auth_key(key):
    temporary_path = KEY_FILE.with_name(f"{KEY_FILE.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(
        temporary_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as key_file:
            key_file.write(key)
        os.replace(temporary_path, KEY_FILE)
        if os.name != "nt":
            KEY_FILE.chmod(0o600)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _log(msg):
    ts = datetime.now().isoformat()
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def _parse_relay_url(url):
    """Split ``host:port`` or ``[v6]:port``; raises ValueError with the field name."""
    text = str(url).strip()
    if text.startswith("["):
        end = text.find("]")
        if end == -1:
            raise ValueError("relay config is corrupt: url")
        host = text[1:end]
        rest = text[end + 1:]
        if not rest.startswith(":") or len(rest) < 2:
            raise ValueError("relay config is corrupt: url")
        port_text = rest[1:]
    else:
        host, separator, port_text = text.rpartition(":")
        if not separator or not host or ":" in host:
            raise ValueError("relay config is corrupt: url")
    if not port_text.isdigit():
        raise ValueError("relay config is corrupt: url")
    port = int(port_text)
    if not 1 <= port <= 65535:
        raise ValueError("relay config is corrupt: url")
    return host, port


def load_relay_config(path):
    """Load and validate the node's relay sidecar, resolving certificate paths.

    Relative ``tls_cert``/``tls_key`` values are resolved against the config
    file's directory so a reloaded config works regardless of the process
    working directory.
    """
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"relay config is unreadable: {exc}") from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"relay config is corrupt: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(  # noqa: TRY004 - a non-object config file is corrupt, not a caller type error
            "relay config is corrupt: expected an object"
        )

    for field in (
        "relay_id",
        "url",
        "node_token",
        "relay_fingerprint",
        "tls_cert",
        "tls_key",
    ):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"relay config is incomplete: {field}")
    if data.get("pool") is None:
        raise ValueError("relay config is incomplete: pool")

    if not RELAY_HEX32.fullmatch(data["relay_id"]):
        raise ValueError("relay config is corrupt: relay_id")
    if not RELAY_HEX64.fullmatch(data["node_token"]):
        raise ValueError("relay config is corrupt: node_token")
    if not RELAY_HEX64.fullmatch(data["relay_fingerprint"]):
        raise ValueError("relay config is corrupt: relay_fingerprint")
    _parse_relay_url(data["url"])

    try:
        pool = int(data["pool"])
    except (TypeError, ValueError) as exc:
        raise ValueError("relay config is corrupt: pool") from exc
    if not 1 <= pool <= 32:
        raise ValueError("relay config is corrupt: pool")

    base = path.parent
    for field in ("tls_cert", "tls_key"):
        candidate = Path(data[field])
        if not candidate.is_absolute():
            candidate = base / candidate
        data[field] = str(candidate.resolve())
    data["pool"] = pool
    data["url"] = data["url"].strip()
    return data


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


class _StandaloneDDoSProtection:
    """Minimal rate-limit/ban fallback used only when core.ddos is absent.

    Mirrors the DDoSProtection interface (check_connection, release_connection,
    on_auth_failure, on_auth_success) so the standalone agent keeps basic
    brute-force protection without the core package.
    """

    def __init__(self, rate_max=30, rate_window=60, conn_per_ip=5,
                 ban_threshold=5, ban_duration=300):
        """Initialize rate-limit, connection, and ban-tracking state."""
        self.rate_max = rate_max
        self.rate_window = rate_window
        self.conn_per_ip = conn_per_ip
        self.ban_threshold = ban_threshold
        self.ban_duration = ban_duration
        self._lock = threading.Lock()
        self._hits = {}
        self._conns = {}
        self._fails = {}
        self._banned_until = {}

    def _now(self):
        """Return the current time in seconds since the epoch."""
        return time.time()

    def _banned(self, ip):
        """Return whether the given IP is currently banned."""
        return self._banned_until.get(ip, 0) > self._now()

    def check_connection(self, ip):
        """Check whether a new connection from the IP is allowed under rate, connection, and ban limits."""
        now = self._now()
        with self._lock:
            if self._banned(ip):
                return False, "IP is banned"
            window_start = now - self.rate_window
            self._hits[ip] = [t for t in self._hits.get(ip, []) if t > window_start]
            if len(self._hits[ip]) >= self.rate_max:
                return False, "Rate limit exceeded"
            if sum(self._conns.values()) >= 100 or self._conns.get(ip, 0) >= self.conn_per_ip:
                return False, "Too many connections"
            self._hits[ip].append(now)
            self._conns[ip] = self._conns.get(ip, 0) + 1
        return True, "OK"

    def release_connection(self, ip):
        """Decrement the active connection count for the given IP."""
        with self._lock:
            if self._conns.get(ip, 0) > 0:
                self._conns[ip] -= 1

    def on_auth_failure(self, ip):
        """Record an authentication failure for the IP, banning it once the threshold is reached."""
        with self._lock:
            fails = self._fails.get(ip, 0) + 1
            self._fails[ip] = fails
            if fails >= self.ban_threshold:
                self._banned_until[ip] = self._now() + self.ban_duration
                return True
        return False

    def on_auth_success(self, ip):
        """Clear any recorded authentication failures for the IP."""
        with self._lock:
            self._fails.pop(ip, None)


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


_BSD_PAGE_SYSCTLS = (
    ("hw.physmem", "vm.stats.vm.v_page_size", "vm.stats.vm.v_free_count", "vm.stats.vm.v_inactive_count"),
    ("hw.physmem", "hw.pagesize", "vm.uvmexp.free"),
    ("hw.physmem64", "hw.pagesize", "vm.uvmexp.free", "vm.uvmexp.inactive"),
)


def _bsd_cpu_percent():
    """CPU busy percentage from vmstat's idle column, 0 on failure."""
    try:
        out = subprocess.run(
            ["vmstat", "1", "2"], capture_output=True, text=True, timeout=10
        ).stdout.strip().splitlines()
        idle = int(out[-1].split()[-1])
        return round(100 - idle, 1) if 0 <= idle <= 100 else 0
    except Exception:
        return 0


def _bsd_ram_usage():
    """Return (total_gb, used_gb, free_gb, percent) via sysctl, zeros on failure."""
    for names in _BSD_PAGE_SYSCTLS:
        try:
            result = subprocess.run(
                ["sysctl", "-n", *names], capture_output=True, text=True, timeout=10
            )
            values = [int(value) for value in result.stdout.split()]
        except Exception:
            continue
        if result.returncode != 0 or len(values) != len(names):
            continue
        total_gb = values[0] / (1024**3)
        free_gb = (sum(values[2:]) * values[1]) / (1024**3)
        used_gb = total_gb - free_gb
        percent = round(used_gb / total_gb * 100, 1) if total_gb > 0 else 0
        return total_gb, used_gb, free_gb, percent
    return 0, 0, 0, 0


def _collect_metrics():
    metrics = {}
    if HAS_PSUTIL:
        cpu = psutil.cpu_percent(interval=0.1)
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
        if _system_os_type() in _BSD_OS_TYPES:
            cpu = _bsd_cpu_percent()
            rt, ru, rf, rp = _bsd_ram_usage()
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


def get_metrics():
    global _METRICS_CACHE, _METRICS_CACHE_AT
    now = time.monotonic()
    with _METRICS_LOCK:
        if (
            _METRICS_CACHE is not None
            and now - _METRICS_CACHE_AT < METRICS_CACHE_SECONDS
        ):
            return deepcopy(_METRICS_CACHE)
        metrics = _collect_metrics()
        _METRICS_CACHE = metrics
        _METRICS_CACHE_AT = time.monotonic()
        return deepcopy(metrics)


def _safe_path(user_path):
    try:
        allowed = (BASE_DIR / "data").resolve()
        allowed.mkdir(parents=True, exist_ok=True)
        resolved = Path(user_path).resolve()
        try:
            resolved.relative_to(allowed)
        except ValueError:
            return None
        real_allowed = Path(os.path.realpath(str(allowed)))
        real_resolved = Path(os.path.realpath(str(resolved)))
        if not (str(real_resolved) == str(real_allowed) or
                str(real_resolved).startswith(str(real_allowed) + os.sep)):
            return None
        return resolved
    except Exception:
        return None


_SAFE_MODES = ("w", "a", "wb", "ab")


def _validate_mode(mode):
    return mode if mode in _SAFE_MODES else None


def _safe_open_write(safe_path, data, mode):
    allowed = (BASE_DIR / "data").resolve()
    append = mode in ("a", "ab")
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    flags |= os.O_APPEND if append else os.O_TRUNC
    fd = os.open(
        str(safe_path),
        flags,
        0o600,
    )
    try:
        real = _resolve_written_path(fd, safe_path)
        if not (str(real) == str(allowed) or str(real).startswith(str(allowed) + os.sep)):
            raise PermissionError("Access denied")
        with os.fdopen(fd, mode) as f:
            if mode in ("wb", "ab") and isinstance(data, str):
                data = data.encode()
            f.write(data)
            fd = None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


BLOCKED_COMMANDS = (
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "format c:",
    "del /s /q c:\\",
    "shutdown",
    "reboot",
    "init 0",
    "init 6",
    "dd if=",
    ">:",
    "chmod -R 777 /",
    "mount /",
    "mv /",
    ":(){",
    "fork bomb",
    "sudo dd",
)


def _normalize_cmd(cmd):
    low = cmd.strip().lower()
    low = low.replace("\\\n", " ")
    import re as _re
    low = _re.sub(r"\s+", " ", low)
    low = low.rstrip(";& ")
    return low


def _command_allowed(cmd):
    low = _normalize_cmd(cmd)
    if not low:
        return False
    for blocked in BLOCKED_COMMANDS:
        norm_blocked = _normalize_cmd(blocked)
        if not norm_blocked:
            continue
        if norm_blocked in low:
            _log(f"BLOCKED_COMMAND: '{cmd}' contains blocked pattern '{blocked}'")
            return False
    dangerous = ("/dev/sd", "/dev/sda", "> /dev/", "pv > /dev/",
                 "--no-preserve-root", "chown -r /", "chmod -r 777 /",
                 ">:", ":(){", "while true", "mkfs", "fdisk", "dd if")
    for d in dangerous:
        if d in low:
            _log(f"BLOCKED_COMMAND: '{cmd}' blocked by dangerous pattern '{d}'")
            return False
    return True


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
        """Listen for valid SPA knocks on all IPv4 interfaces until stopped.

        Call on_open with the window in seconds and source IP for each valid
        packet. Bind failures return; receive, validation, and callback errors
        are suppressed while listening continues. Socket setup errors propagate.
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.settimeout(1.0)
        try:
            # nosec B104 -- SPA knock listener. Every packet is HMAC-validated with
            # compare_digest before it can open the TCP port, and the listener must
            # be reachable off-host for knocks to arrive at all.
            self._sock.bind(("0.0.0.0", self.spa_port))  # nosec B104
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


def _close_socket(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


class RelayClient:
    """Keep ``pool`` outbound TLS slots parked at the relay.

    Each slot thread registers, answers keepalives, and hands a paired inner
    TLS socket to :meth:`NodeAgent._handle`. A supervisor respawns slot threads
    that exit and the slot loop reconnects with exponential backoff.
    """

    def __init__(self, agent, config, connect_timeout=10.0):
        self.agent = agent
        self.relay_id = config["relay_id"]
        self.url = config["url"]
        self.node_token = config["node_token"]
        self.relay_fingerprint = config["relay_fingerprint"]
        self.tls_cert = config["tls_cert"]
        self.tls_key = config["tls_key"]
        self.pool_size = int(config.get("pool", 4))
        self.connect_timeout = connect_timeout
        self._host, self._port = _parse_relay_url(self.url)
        self._inner_context = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads = []
        self._sockets = set()
        self._connected = 0
        self._last_error = None
        self._last_connected_at = None
        self._supervisor = None

    def start(self):
        with self._lock:
            if self._supervisor is not None:
                return
            self._stop.clear()
            supervisor = threading.Thread(
                target=self._supervise, name="relay-supervisor", daemon=True
            )
            self._supervisor = supervisor
        supervisor.start()

    def stop(self):
        self._stop.set()
        with self._lock:
            sockets = list(self._sockets)
            threads = list(self._threads)
            supervisor = self._supervisor
            self._supervisor = None
        for sock in sockets:
            _close_socket(sock)
        deadline = time.monotonic() + 2.0
        for thread in [*threads, supervisor]:
            if thread is None or thread is threading.current_thread():
                continue
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        with self._lock:
            self._threads = []
            self._sockets.clear()
            self._connected = 0

    def status(self):
        with self._lock:
            return {
                "enabled": True,
                "url": self.url,
                "connected_slots": self._connected,
                "pool_size": self.pool_size,
                "last_error": self._last_error,
                "last_connected_at": self._last_connected_at,
            }

    def _supervise(self):
        while not self._stop.is_set():
            with self._lock:
                self._threads = [t for t in self._threads if t.is_alive()]
                missing = self.pool_size - len(self._threads)
                for _ in range(max(0, missing)):
                    slot = threading.Thread(
                        target=self._run_slot, name="relay-slot", daemon=True
                    )
                    self._threads.append(slot)
                    slot.start()
            self._stop.wait(0.5)

    def _run_slot(self):
        backoff = RELAY_BACKOFF_INITIAL
        while not self._stop.is_set():
            state = {"registered": False}
            try:
                self._serve_once(state)
            except (cloudmesh_relay.RelayError, ssl.SSLError, OSError) as exc:
                if self._stop.is_set():
                    return
                self._record_error(str(exc))
            if self._stop.is_set():
                return
            if state["registered"]:
                backoff = RELAY_BACKOFF_INITIAL
            delay = min(
                backoff * random.uniform(0.8, 1.2), RELAY_BACKOFF_MAX
            )
            self._stop.wait(delay)
            backoff = min(backoff * 2, RELAY_BACKOFF_MAX)

    def _serve_once(self, state):
        sock = cloudmesh_relay.open_outer_tls(
            self._host,
            self._port,
            self.relay_fingerprint,
            timeout=self.connect_timeout,
        )
        self._track(sock)
        registered = False
        try:
            ts = int(time.time())
            nonce = secrets.token_hex(8)
            cloudmesh_relay.send_frame(
                sock,
                {
                    "type": "register",
                    "relay_id": self.relay_id,
                    "ts": ts,
                    "nonce": nonce,
                    "mac": cloudmesh_relay.register_mac(
                        self.node_token, self.relay_id, ts, nonce
                    ),
                },
            )
            reply = cloudmesh_relay.recv_frame(sock)
            if not reply or reply.get("type") != "parked":
                message = (reply or {}).get("message", "the relay closed the connection")
                raise cloudmesh_relay.RelayError(
                    f"relay registration failed: {message}"
                )
            state["registered"] = True
            registered = True
            self._on_registered()

            paired = self._wait_for_pair(sock)
            client_id = str(paired.get("client_id") or "")
            if not RELAY_HEX32.fullmatch(client_id):
                raise cloudmesh_relay.RelayError(
                    "relay pairing failed: invalid client id"
                )
            self._on_paired()
            registered = False

            inner = cloudmesh_relay.wrap_inner_tls(
                sock,
                self._inner_tls_context(),
                server_side=True,
                timeout=RELAY_PARKED_READ_TIMEOUT,
            )
            self.agent._handle(inner, ("relay", 0), client_id=client_id)
        finally:
            if registered:
                self._on_unregistered()
            self._untrack(sock)
            _close_socket(sock)

    def _wait_for_pair(self, sock):
        sock.settimeout(RELAY_PARKED_READ_TIMEOUT)
        while True:
            message = cloudmesh_relay.recv_frame(sock)
            if message is None:
                raise cloudmesh_relay.RelayError(
                    "relay closed the parked connection"
                )
            kind = message.get("type")
            if kind == "ping":
                cloudmesh_relay.send_frame(sock, {"type": "pong"})
                continue
            if kind == "paired":
                return message
            if kind == "error":
                raise cloudmesh_relay.RelayError(
                    "relay rejected the connection: "
                    + str(message.get("message", "unknown error"))
                )
            raise cloudmesh_relay.RelayError(
                f"relay sent an unexpected frame: {kind}"
            )

    def _inner_tls_context(self):
        if self._inner_context is not None:
            return self._inner_context
        for label, path in (("tls_cert", self.tls_cert), ("tls_key", self.tls_key)):
            if not Path(path).is_file():
                raise cloudmesh_relay.RelayError(
                    f"relay inner TLS is not configured: {label} not found"
                )
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.tls_cert, self.tls_key)
        self._inner_context = context
        return context

    def _track(self, sock):
        with self._lock:
            self._sockets.add(sock)

    def _untrack(self, sock):
        with self._lock:
            self._sockets.discard(sock)

    def _record_error(self, message):
        with self._lock:
            self._last_error = message

    def _on_registered(self):
        with self._lock:
            self._connected += 1
            self._last_error = None
            self._last_connected_at = datetime.now().isoformat(timespec="seconds")

    def _on_paired(self):
        self._on_unregistered()

    def _on_unregistered(self):
        with self._lock:
            self._connected = max(0, self._connected - 1)


class NodeAgent:
    def __init__(self, port=DEFAULT_PORT, auth_key=None, bind_host="0.0.0.0",  # nosec B104 -- node agent must be reachable by design; every request is auth-gated
                 tls_cert=None, tls_key=None,
                 spa=False, spa_port=DEFAULT_SPA_PORT, spa_window=DEFAULT_SPA_WINDOW,
                 relay_config=None, relay_only=False):
        """Initialize the node agent's listener, job store, and DDoS protection.

        Use `auth_key` when nonempty, otherwise read or create the persistent
        node key. Create the job directory and reload jobs, marking previously
        running jobs unknown. Listener settings take effect when serve is called;
        `spa_window` is the TCP access window in seconds after a valid knock.
        `relay_config` enables the outbound relay pool; `relay_only` keeps the
        inbound TCP listener closed. Raise ValueError if only one TLS path is
        supplied, or if relay_only is set without a relay config. Auth-key and
        job directory I/O errors propagate; errors reading individual jobs are
        skipped.
        """
        if bool(tls_cert) != bool(tls_key):
            raise ValueError("--tls-cert and --tls-key must be supplied together")
        if relay_only and relay_config is None:
            raise ValueError("--relay-only requires --relay-config")
        self.port = port
        self.auth_key = auth_key or get_or_create_key()
        self.bind_host = bind_host
        self.tls_cert = tls_cert
        self.tls_key = tls_key
        self._running = False
        self._jobs = {}
        self._job_processes = {}
        self._lock = threading.Lock()
        self._load_jobs()

        self.spa_mode = spa
        self.spa_port = spa_port
        self.spa_window = spa_window
        self._spa_open = False
        self._spa_lock = threading.Lock()
        self._spa_event = threading.Event()
        self._spa_expire = 0.0

        try:
            from core.ddos import DDoSProtection
        except ImportError:
            try:
                from cloudmesh.core.ddos import DDoSProtection
            except ImportError:
                DDoSProtection = None
        if DDoSProtection is not None:
            self._ddos = DDoSProtection()
        else:
            # Standalone fallback: the agent is deployed without the core
            # package, so a missing DDoS module must never prevent startup.
            self._ddos = _StandaloneDDoSProtection()
        self._spac = None

        self.relay_config = relay_config
        self.relay_only = relay_only
        self._relay_client = RelayClient(self, relay_config) if relay_config else None
        self._received_bytes = 0
        self._stop_event = threading.Event()

    def _on_spa_knock(self, window, source_ip):
        now = time.time()
        with self._spa_lock:
            if not self._spa_open:
                self._spa_open = True
                self._spa_event.set()
                try:
                    subprocess.run(
                        ["iptables", "-I", "INPUT", "-p", "tcp", "--dport", str(self.port),
                         "-s", source_ip, "-j", "ACCEPT"],
                        capture_output=True, timeout=5
                    )
                    _log(f"SPA: iptables ACCEPT rule added for TCP {self.port} from {source_ip}")
                except Exception as e:
                    _log(f"SPA: iptables failed: {e}")
            self._spa_expire = now + window

        def close_after_delay():
            while True:
                with self._spa_lock:
                    remaining = self._spa_expire - time.time()
                    if remaining <= 0:
                        self._spa_open = False
                        self._spa_event.clear()
                        self._spa_expire = 0.0
                        break
                time.sleep(min(remaining, 0.5))
            try:
                subprocess.run(
                    ["iptables", "-D", "INPUT", "-p", "tcp", "--dport", str(self.port),
                     "-s", source_ip, "-j", "ACCEPT"],
                    capture_output=True, timeout=5
                )
                _log(f"SPA: iptables ACCEPT rule removed for TCP {self.port} from {source_ip}")
            except Exception as e:
                _log(f"SPA: iptables cleanup failed: {e}")
            _log(f"SPA: TCP port {self.port} closed")

        if not any(
            hasattr(t, "_cm_spa_closer") and getattr(t, "_cm_spa_closer", False)
            for t in threading.enumerate()
        ):
            t = threading.Thread(target=close_after_delay, daemon=True)
            t._cm_spa_closer = True
            t.start()

    def _load_jobs(self):
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        for f in JOBS_DIR.glob("*.json"):
            try:
                job = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(job, dict) or not isinstance(job.get("id"), str):
                    raise ValueError("Persisted job must contain a string ID")
                if job.get("status") == "running":
                    job["status"] = "unknown"
                    job["stderr"] = (
                        "The node agent restarted while this job was running; "
                        "its final outcome could not be confirmed."
                    )
                    self._save_job(job)
                self._jobs[job["id"]] = job
            except (OSError, UnicodeError, ValueError) as exc:
                _log(f"Could not load persisted job {f.name}: {exc}")

    def _save_job(self, job):
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        path = JOBS_DIR / f"{job['id']}.json"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=JOBS_DIR
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as job_file:
                json.dump(job, job_file, indent=2)
            os.replace(temporary_path, path)
            if os.name != "nt":
                path.chmod(0o600)
        finally:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass

    def _count_received(self, size):
        with self._lock:
            self._received_bytes += size

    def received_application_bytes(self):
        with self._lock:
            return self._received_bytes

    def relay_status(self):
        if self._relay_client is None:
            return {"enabled": False}
        return self._relay_client.status()

    @property
    def info(self):
        relay_state = (
            self._relay_client.status() if self._relay_client else {"enabled": False}
        )
        return {
            "node_id": get_node_id(),
            "hostname": socket.gethostname(),
            "platform": sys.platform,
            "arch": platform.machine(),
            "python": platform.python_version(),
            "spa_mode": self.spa_mode,
            "relay": relay_state,
        }

    def start_relay_only_for_test(self):
        if self._relay_client is None:
            raise ValueError("relay client is not configured")
        self._relay_client.start()

    def stop_relay_for_test(self):
        if self._relay_client is not None:
            self._relay_client.stop()

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._relay_client is not None:
            self._relay_client.stop()
        if self._spac is not None:
            self._spac.stop()

    def _recv_msg(self, sock, max_size=50 * 1024 * 1024):
        header_timeout = 10
        read_timeout = 60
        try:
            sock.settimeout(header_timeout)
        except Exception:
            pass
        header = b""
        while len(header) < 4:
            try:
                chunk = sock.recv(4 - len(header))
            except socket.timeout:
                return None
            if not chunk:
                return None
            self._count_received(len(chunk))
            header += chunk
        length = int.from_bytes(header, "big")
        if length > max_size or length <= 0:
            return None
        try:
            sock.settimeout(read_timeout)
        except Exception:
            pass
        data = b""
        while len(data) < length:
            try:
                chunk = sock.recv(min(length - len(data), 65536))
            except socket.timeout:
                return None
            if not chunk:
                break
            self._count_received(len(chunk))
            data += chunk
        try:
            return json.loads(data.decode())
        except Exception:
            return None

    def _send_msg(self, sock, resp):
        msg = json.dumps(resp).encode()
        sock.sendall(len(msg).to_bytes(4, "big") + msg)

    def _handle_execute(self, cmd, timeout=300):
        if len(cmd) > 65536:
            return {"success": False, "exit_code": -1, "stdout": "",
                    "stderr": "Command too long"}
        if not _command_allowed(cmd):
            return {"success": False, "exit_code": -1, "stdout": "",
                    "stderr": "Command blocked by security policy"}
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
        if len(cmd) > 65536:
            return {"job_id": None, "status": "blocked",
                    "stderr": "Command too long"}
        if not _command_allowed(cmd):
            return {"job_id": None, "status": "blocked",
                    "stderr": "Command blocked by security policy"}
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
            timed_out = False
            try:
                kwargs = {
                    "shell": True, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
                    "text": True,
                }
                if os.name == "nt":
                    kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                else:
                    kwargs["start_new_session"] = True
                with self._lock:
                    if job["status"] == "cancelled":
                        return
                proc = subprocess.Popen(cmd, **kwargs)
                with self._lock:
                    self._job_processes[job_id] = proc
                    cancelled = job["status"] == "cancelled"
                if cancelled:
                    self._terminate_job_process(proc)
                try:
                    stdout, stderr = proc.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    self._terminate_job_process(proc)
                    stdout, stderr = proc.communicate()
                    with self._lock:
                        if job["status"] != "cancelled":
                            job["status"] = "failed"
                            job["stderr"] = "Timeout"
                            job["exit_code"] = -1
                            timed_out = True
                with self._lock:
                    if job["status"] != "cancelled" and not timed_out:
                        job["exit_code"] = proc.returncode
                        job["stdout"] = stdout
                        job["stderr"] = stderr
                        job["status"] = "completed" if proc.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                with self._lock:
                    if job["status"] != "cancelled":
                        job["status"] = "failed"
                        job["stderr"] = "Timeout"
                        job["exit_code"] = -1
            except Exception as e:
                with self._lock:
                    if job["status"] != "cancelled":
                        job["status"] = "failed"
                        job["stderr"] = str(e)
                        job["exit_code"] = -1
            finally:
                with self._lock:
                    self._job_processes.pop(job_id, None)
                    if job["status"] != "cancelled":
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
            if job["status"] != "running":
                return {"success": False, "message": f"Job status: {job['status']}"}
            job["status"] = "cancelled"
            job["finished_at"] = datetime.now().isoformat()
            proc = self._job_processes.get(job_id)
            self._save_job(job)
        if proc is not None:
            self._terminate_job_process(proc)
        return {"success": True, "message": f"Job {job_id} cancelled"}

    @staticmethod
    def _terminate_job_process(proc):
        if proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True, timeout=10,
                )
            else:
                os.killpg(proc.pid, signal.SIGTERM)
        except (OSError, subprocess.SubprocessError):
            try:
                proc.terminate()
            except OSError:
                pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        capture_output=True, timeout=10,
                    )
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
            except (OSError, subprocess.SubprocessError):
                proc.kill()

    def _handle(self, client, addr, client_id=None):
        ip = addr[0]
        scope = client_id or ip
        if client_id:
            _log(f"Relay: paired client {client_id[:8]}")
        try:
            allowed, reason = self._ddos.check_connection(scope)
            if not allowed:
                _log(f"DDoS: Rejected {scope}: {reason}")
                self._send_msg(client, {"type": "error", "message": "Rejected"})
                return

            req = self._recv_msg(client)
            if req is None:
                return

            auth_key = req.get("auth", "") or ""
            if not hmac_mod.compare_digest(auth_key, self.auth_key):
                _log(f"AUTH_FAIL: {ip}")
                is_banned = self._ddos.on_auth_failure(scope)
                is_tripwire, tripwire_name = _check_tripwire(auth_key)
                if is_tripwire:
                    _log(f"TRIPWIRE TRIGGERED! Key '{tripwire_name}' used from {ip}")
                    _log_tripwire_breach(auth_key, ip)
                if is_banned:
                    _log(f"DDoS: IP {scope} banned after repeated auth failures")
                self._send_msg(client, {"type": "error", "message": "Auth failed"})
                return

            self._ddos.on_auth_success(scope)

            action = req.get("action", "")
            if action == "ping":
                resp = {"type": "pong", "time": datetime.now().isoformat()}
            elif action == "info":
                resp = {"type": "info", "data": self.info}
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
                        mode = _validate_mode(req.get("data", {}).get("mode", "w"))
                        if mode is None:
                            resp = {"type": "upload", "data": {"success": False, "message": "Invalid file mode"}}
                        else:
                            _safe_open_write(safe, req.get("data", {}).get("content", ""), mode)
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
                elif safe.is_symlink():
                    resp = {"type": "download", "data": {"success": False, "message": "Access denied"}}
                else:
                    try:
                        allowed = (BASE_DIR / "data").resolve()
                        real_resolved = Path(os.path.realpath(str(safe)))
                        if not (str(real_resolved) == str(allowed) or
                                str(real_resolved).startswith(str(allowed) + os.sep)):
                            raise PermissionError("Access denied")
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
                    _write_auth_key(new_key)
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
            self._ddos.release_connection(scope)
            try:
                client.close()
            except Exception:
                pass

    def serve(self):
        if self.spa_mode:
            guard = _spa_guard(platform.system())
            if guard:
                _log(guard)
                return

        self._running = True
        self._stop_event.clear()
        PID_FILE.write_text(str(os.getpid()))

        if self._relay_client is not None:
            self._relay_client.start()
            _log(
                f"Relay: {self._relay_client.url} "
                f"(pool {self._relay_client.pool_size})"
            )

        if self.relay_only:
            _log("Relay-only mode: inbound TCP listener disabled")
            while self._running:
                self._stop_event.wait(0.2)
            self._shutdown()
            return

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
        self._shutdown()

    def _shutdown(self):
        if self._relay_client is not None:
            self._relay_client.stop()
        if self._spac is not None:
            self._spac.stop()
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
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


def cmd_start(port=DEFAULT_PORT, bind_host="0.0.0.0",  # nosec B104 -- default bind only; --bind overrides it, and requests are auth-gated
              tls_cert=None, tls_key=None, spa=False, spa_port=DEFAULT_SPA_PORT, spa_window=DEFAULT_SPA_WINDOW,
              relay_config=None, relay_only=False):
    """Run the node agent in the foreground unless its recorded PID is alive.

    Pass listener, TLS, SPA, and relay settings to NodeAgent; `spa_window` is
    the TCP access window in seconds after a valid knock. Suppress
    KeyboardInterrupt during serving. Construction and startup errors,
    including invalid TLS pairs, propagate.
    """
    existing = _read_pid()
    if existing and _is_running(existing):
        print(f"Already running (PID {existing})")
        return
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    agent = NodeAgent(port=port, bind_host=bind_host, tls_cert=tls_cert, tls_key=tls_key,
                      spa=spa, spa_port=spa_port, spa_window=spa_window,
                      relay_config=relay_config, relay_only=relay_only)
    mode_str = f"SPA(UDP:{spa_port}, window:{spa_window}s)" if spa else "TCP"
    if relay_config:
        mode_str += f" + relay {relay_config['url']} (pool {relay_config['pool']})"
    if relay_only:
        mode_str += " (relay only)"
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
    """Parse node start/stop/status arguments and dispatch the selected command.

    Print help when no command is given. Invalid arguments or incomplete TLS
    pairs raise SystemExit; command handler errors propagate.
    """
    import argparse
    p = argparse.ArgumentParser(description="CloudMesh Node")
    sub = p.add_subparsers(dest="command")
    start_p = sub.add_parser("start")
    start_p.add_argument("--port", "-p", type=int, default=DEFAULT_PORT)
    start_p.add_argument("--bind", "-b", default="0.0.0.0")  # nosec B104 -- operator-settable default for a deliberately network-facing agent
    start_p.add_argument("--tls-cert", default=None)
    start_p.add_argument("--tls-key", default=None)
    start_p.add_argument("--spa", action="store_true",
                         help="Enable SPA (Single Packet Authorization) — TCP port invisible to scanners")
    start_p.add_argument("--spa-port", type=int, default=DEFAULT_SPA_PORT,
                         help="UDP port for SPA knocks (default: 9998)")
    start_p.add_argument("--spa-window", type=int, default=DEFAULT_SPA_WINDOW,
                         help="Seconds TCP port stays open after knock (default: 5)")
    start_p.add_argument("--relay-config", default=None,
                         help="Node relay sidecar written by `cm node relay enable`")
    start_p.add_argument("--relay-only", action="store_true",
                         help="Keep the inbound TCP listener closed and serve only through the relay")
    sub.add_parser("stop")
    sub.add_parser("status")
    sub.add_parser("relay", add_help=False)
    args, unknown = p.parse_known_args()
    if args.command == "start":
        if bool(args.tls_cert) != bool(args.tls_key):
            p.error("both --tls-cert and --tls-key must be supplied together")
        if args.relay_only and not args.relay_config:
            p.error("--relay-only requires --relay-config")
        relay_config = None
        if args.relay_config:
            try:
                relay_config = load_relay_config(Path(args.relay_config))
            except ValueError as exc:
                p.error(str(exc))
        cmd_start(port=args.port, bind_host=args.bind, tls_cert=args.tls_cert, tls_key=args.tls_key,
                  spa=args.spa, spa_port=args.spa_port, spa_window=args.spa_window,
                  relay_config=relay_config, relay_only=args.relay_only)
    elif args.command == "stop":
        cmd_stop()
    elif args.command == "status":
        cmd_status()
    elif args.command == "relay":
        return cloudmesh_relay.main(unknown)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
