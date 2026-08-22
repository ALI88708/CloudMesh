import time
import threading
import json
import os
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class RateLimiter:
    def __init__(self, max_requests=30, window=60):
        self.max_requests = max_requests
        self.window = window
        self._requests = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, ip):
        now = time.time()
        with self._lock:
            self._requests[ip] = [t for t in self._requests[ip] if now - t < self.window]
            if len(self._requests[ip]) >= self.max_requests:
                return False
            self._requests[ip].append(now)
            return True

    def get_count(self, ip):
        now = time.time()
        with self._lock:
            self._requests[ip] = [t for t in self._requests[ip] if now - t < self.window]
            return len(self._requests[ip])

    def reset(self, ip):
        with self._lock:
            self._requests.pop(ip, None)


class ConnectionLimiter:
    def __init__(self, max_per_ip=5, max_total=100):
        self.max_per_ip = max_per_ip
        self.max_total = max_total
        self._per_ip = defaultdict(int)
        self._total = 0
        self._lock = threading.Lock()

    def can_accept(self, ip):
        with self._lock:
            if self._total >= self.max_total:
                return False
            if self._per_ip[ip] >= self.max_per_ip:
                return False
            self._per_ip[ip] += 1
            self._total += 1
            return True

    def release(self, ip):
        with self._lock:
            self._per_ip[ip] = max(0, self._per_ip[ip] - 1)
            self._total = max(0, self._total - 1)

    def get_stats(self):
        with self._lock:
            return {"total": self._total, "per_ip": dict(self._per_ip)}


class IPBlacklister:
    def __init__(self, fail_threshold=5, ban_duration=300):
        self.fail_threshold = fail_threshold
        self.ban_duration = ban_duration
        self._failures = defaultdict(int)
        self._bans = {}
        self._lock = threading.Lock()
        self._load_bans()

    def _bans_file(self):
        return os.path.join(DATA_DIR, "banned_ips.json")

    def _load_bans(self):
        p = self._bans_file()
        if os.path.exists(p):
            try:
                with open(p) as f:
                    data = json.load(f)
                now = time.time()
                for ip, info in data.items():
                    if info.get("expires", 0) > now:
                        self._bans[ip] = info
            except Exception:
                pass

    def _save_bans(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self._bans_file(), "w") as f:
            json.dump(self._bans, f, indent=2)

    def record_failure(self, ip):
        with self._lock:
            self._failures[ip] += 1
            if self._failures[ip] >= self.fail_threshold:
                self._bans[ip] = {
                    "expires": time.time() + self.ban_duration,
                    "reason": f"{self._failures[ip]} auth failures",
                    "banned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                self._failures[ip] = 0
                self._save_bans()
                return True
            return False

    def record_success(self, ip):
        with self._lock:
            self._failures.pop(ip, None)

    def is_banned(self, ip):
        with self._lock:
            if ip in self._bans:
                if time.time() > self._bans[ip]["expires"]:
                    del self._bans[ip]
                    self._save_bans()
                    return False
                return True
            return False

    def ban(self, ip, reason="manual"):
        with self._lock:
            self._bans[ip] = {
                "expires": time.time() + self.ban_duration,
                "reason": reason,
                "banned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._save_bans()

    def unban(self, ip):
        with self._lock:
            self._bans.pop(ip, None)
            self._save_bans()

    def get_banned(self):
        now = time.time()
        with self._lock:
            self._bans = {k: v for k, v in self._bans.items() if v.get("expires", 0) > now}
            return dict(self._bans)


class PacketValidator:
    MAX_PACKET_SIZE = 1024 * 1024
    MIN_PACKET_SIZE = 10
    MAX_JSON_DEPTH = 5

    @staticmethod
    def validate(data):
        if len(data) > PacketValidator.MAX_PACKET_SIZE:
            return False, "Packet too large"
        if len(data) < PacketValidator.MIN_PACKET_SIZE:
            return False, "Packet too small"
        try:
            parsed = json.loads(data)
        except Exception:
            return False, "Invalid JSON"
        if not isinstance(parsed, dict):
            return False, "JSON must be object"
        if "action" not in parsed:
            return False, "Missing action field"
        if len(json.dumps(parsed)) > PacketValidator.MAX_PACKET_SIZE:
            return False, "Payload too large"
        return True, parsed


class SlowlorisGuard:
    def __init__(self, read_timeout=10):
        self.read_timeout = read_timeout

    def check(self, sock):
        sock.settimeout(self.read_timeout)
        try:
            data = sock.recv(4)
            if not data:
                return False, "No data received"
            length = int.from_bytes(data, "big")
            if length > 50 * 1024 * 1024:
                return False, f"Header claims {length} bytes — too large"
            return True, length
        except Exception:
            return False, "Read timeout"


class DDoSProtection:
    def __init__(self, rate_max=30, rate_window=60, conn_per_ip=5, conn_total=100,
                 ban_threshold=5, ban_duration=300, read_timeout=10):
        self.rate_limiter = RateLimiter(rate_max, rate_window)
        self.connection_limiter = ConnectionLimiter(conn_per_ip, conn_total)
        self.blacklister = IPBlacklister(ban_threshold, ban_duration)
        self.packet_validator = PacketValidator()
        self.slowloris_guard = SlowlorisGuard(read_timeout)
        self._stats = {"dropped": 0, "accepted": 0, "banned": 0}
        self._lock = threading.Lock()

    def check_connection(self, ip):
        if self.blacklister.is_banned(ip):
            with self._lock:
                self._stats["banned"] += 1
            return False, "IP is banned"
        if not self.rate_limiter.is_allowed(ip):
            with self._lock:
                self._stats["dropped"] += 1
            return False, "Rate limit exceeded"
        if not self.connection_limiter.can_accept(ip):
            with self._lock:
                self._stats["dropped"] += 1
            return False, "Too many connections"
        with self._lock:
            self._stats["accepted"] += 1
        return True, "OK"

    def release_connection(self, ip):
        self.connection_limiter.release(ip)

    def on_auth_failure(self, ip):
        return self.blacklister.record_failure(ip)

    def on_auth_success(self, ip):
        self.blacklister.record_success(ip)

    def get_stats(self):
        with self._lock:
            stats = dict(self._stats)
        stats["banned_ips"] = self.blacklister.get_banned()
        stats["connections"] = self.connection_limiter.get_stats()
        return stats
