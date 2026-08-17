import json
import time
import socket
import subprocess
import threading
import http.server
import hashlib
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor


# === 1. AUTO-DISCOVERY ===

def discover_network(subnet="192.168.1", port=9999, timeout=0.3):
    found = []
    base = subnet.rstrip(".")

    def scan_host(ip):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            if s.connect_ex((ip, port)) == 0:
                s.sendall(json.dumps({"action": "ping", "auth": ""}).encode())
                data = s.recv(4096)
                s.close()
                try:
                    resp = json.loads(data)
                    if resp.get("type") == "pong":
                        return {"ip": ip, "port": port, "status": "open"}
                except Exception:
                    return {"ip": ip, "port": port, "status": "open"}
            s.close()
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=50) as pool:
        futures = [pool.submit(scan_host, f"{base}.{i}") for i in range(1, 255)]
        for f in futures:
            r = f.result()
            if r:
                found.append(r)
    return found


# === 2. BENCHMARK ===

def benchmark_cpu(duration=3):
    import time as _t
    start = _t.time()
    count = 0
    while _t.time() - start < duration:
        hashlib.md5(str(count).encode()).hexdigest()
        count += 1
    ops = count / duration
    return {"score": round(ops), "duration": duration}

def benchmark_disk(path=None, size_mb=10):
    import os, tempfile
    path = path or tempfile.gettempdir()
    test_file = os.path.join(path, "_cm_bench_test.tmp")
    data = os.urandom(size_mb * 1024 * 1024)
    start = time.time()
    with open(test_file, "wb") as f:
        f.write(data)
    write_time = time.time() - start
    start = time.time()
    with open(test_file, "rb") as f:
        f.read()
    read_time = time.time() - start
    try:
        os.remove(test_file)
    except Exception:
        pass
    return {
        "write_mb_s": round(size_mb / write_time, 1),
        "read_mb_s": round(size_mb / read_time, 1),
        "write_time": round(write_time, 3),
        "read_time": round(read_time, 3),
    }

def benchmark_ram(size_mb=64):
    import time as _t
    start = _t.time()
    data = [bytearray(1024 * 1024) for _ in range(size_mb)]
    alloc_time = _t.time() - start
    start = _t.time()
    for chunk in data:
        chunk[0] = 0xFF
    access_time = _t.time() - start
    del data
    return {
        "alloc_time": round(alloc_time, 3),
        "access_time": round(access_time, 3),
        "size_mb": size_mb,
    }

def run_full_benchmark(server_mgr=None, name=None):
    if server_mgr and name:
        cmd = """python3 -c "
import time, hashlib, os, tempfile
start=time.time(); c=0
while time.time()-start<2: c+=hashlib.md5(str(c).encode()).hexdigest().encode()
cpu_score=round(1000000/(time.time()-start))
f=os.path.join(tempfile.gettempdir(),'_b'); d=os.urandom(10*1024*1024)
s=time.time(); open(f,'wb').write(d); wt=time.time()-s
s=time.time(); open(f,'rb').read(); rt=time.time()-s
try: os.remove(f)
except: pass
print(json.dumps({'cpu_score':cpu_score,'write_mb_s':round(10/wt,1),'read_mb_s':round(10/rt,1)}))
" 2>/dev/null"""
        try:
            r = server_mgr.execute(name, "python3 -c \"import time,hashlib,os,tempfile,json;s=time.time();c=0;" \
                "exec('while time.time()-s<2:\\n c+=hashlib.md5(str(c).encode()).hexdigest().encode()');" \
                "cs=round(1000000/(time.time()-s));f=os.path.join(tempfile.gettempdir(),'_b');" \
                "d=os.urandom(10*1048576);t=time.time();open(f,'wb').write(d);wt=time.time()-t;" \
                "t=time.time();open(f,'rb').read();rt=time.time()-t;" \
                "exec('try:\\n os.remove(f)\\nexcept:\\n pass');" \
                "print(json.dumps({\"cpu\":cs,\"w\":round(10/wt,1),\"r\":round(10/rt,1)}))\"")
            if r["exit_code"] == 0:
                return json.loads(r["stdout"])
        except Exception:
            pass
    return {"cpu": benchmark_cpu(2), "disk": benchmark_disk(), "ram": benchmark_ram(32)}


# === 3. SCHEDULE ===

class ScheduleManager:
    def __init__(self, schedule_file=None):
        self.file = Path(schedule_file or Path(__file__).parent.parent / ".schedule.json")
        self._schedules = self._load()

    def _load(self):
        if self.file.exists():
            try:
                return json.loads(self.file.read_text())
            except Exception:
                pass
        return {}

    def _save(self):
        self.file.write_text(json.dumps(self._schedules, indent=2))

    def add(self, name, command, interval_seconds=3600, server=None):
        self._schedules[name] = {
            "command": command,
            "interval": interval_seconds,
            "server": server,
            "created": datetime.now().isoformat(),
            "last_run": None,
            "run_count": 0,
            "enabled": True,
        }
        self._save()
        return True

    def remove(self, name):
        if name in self._schedules:
            del self._schedules[name]
            self._save()
            return True
        return False

    def list_all(self):
        return self._schedules

    def get_next_run(self, name):
        s = self._schedules.get(name)
        if not s or not s["enabled"]:
            return None
        last = s.get("last_run")
        if not last:
            return "now"
        from datetime import timedelta
        last_dt = datetime.fromisoformat(last)
        next_dt = last_dt + timedelta(seconds=s["interval"])
        remaining = (next_dt - datetime.now()).total_seconds()
        if remaining <= 0:
            return "now"
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        return f"{mins}m {secs}s"

    def toggle(self, name, enabled=None):
        if name in self._schedules:
            if enabled is None:
                enabled = not self._schedules[name]["enabled"]
            self._schedules[name]["enabled"] = enabled
            self._save()
            return True
        return False


# === 4. TELEGRAM / DISCORD NOTIFICATIONS ===

class NotifyManager:
    def __init__(self, notify_file=None):
        self.file = Path(notify_file or Path(__file__).parent.parent / ".notify.json")
        self._config = self._load()

    def _load(self):
        if self.file.exists():
            try:
                return json.loads(self.file.read_text())
            except Exception:
                pass
        return {"telegram": {}, "discord": {}}

    def _save(self):
        self.file.write_text(json.dumps(self._config, indent=2))

    def setup_telegram(self, bot_token, chat_id):
        self._config["telegram"] = {"bot_token": bot_token, "chat_id": chat_id}
        self._save()

    def setup_discord(self, webhook_url):
        self._config["discord"] = {"webhook_url": webhook_url}
        self._save()

    def send_telegram(self, message):
        t = self._config.get("telegram", {})
        if not t.get("bot_token") or not t.get("chat_id"):
            return False
        try:
            import urllib.request
            url = f"https://api.telegram.org/bot{t['bot_token']}/sendMessage"
            data = json.dumps({"chat_id": t["chat_id"], "text": message}).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception:
            return False

    def send_discord(self, message):
        d = self._config.get("discord", {})
        if not d.get("webhook_url"):
            return False
        try:
            import urllib.request
            data = json.dumps({"content": message}).encode()
            req = urllib.request.Request(d["webhook_url"], data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception:
            return False

    def notify(self, message):
        results = {}
        results["telegram"] = self.send_telegram(message)
        results["discord"] = self.send_discord(message)
        return results

    def get_status(self):
        t = self._config.get("telegram", {})
        d = self._config.get("discord", {})
        return {
            "telegram": "configured" if t.get("bot_token") else "not configured",
            "discord": "configured" if d.get("webhook_url") else "not configured",
        }


# === 5. REST API ===

import secrets

class CloudMeshAPI:
    def __init__(self, server_mgr=None, monitor=None, node_keys=None, port=8080, api_key=None):
        self.server_mgr = server_mgr
        self.monitor = monitor
        self.node_keys = node_keys or {}
        self.port = port
        self._running = False
        self.api_key = api_key or secrets.token_hex(32)

    def _handle(self, request):
        import urllib.parse
        parsed = urllib.parse.urlparse(request.path)
        path = parsed.path.rstrip("/")
        params = urllib.parse.parse_qs(parsed.query)

        api_key = request.headers.get("X-Api-Key", "")
        if not secrets.compare_digest(api_key, self.api_key):
            return {"error": "Unauthorized"}, 401

        if path == "/api/status":
            return {"status": "ok", "version": "1.0.0", "time": datetime.now().isoformat()}
        elif path == "/api/servers":
            servers = {}
            if self.server_mgr:
                for name in self.server_mgr.list_servers():
                    try:
                        m = self.monitor.get_all_metrics(name) if self.monitor else None
                        servers[name] = m
                    except Exception:
                        servers[name] = None
            return {"servers": servers}
        elif path == "/api/nodes":
            safe_nodes = {}
            for name, info in self.node_keys.items():
                safe_nodes[name] = {
                    "host": info.get("host", ""),
                    "port": info.get("port", 9999),
                }
            return {"nodes": safe_nodes}
        elif path.startswith("/api/exec/"):
            server = path.split("/")[-1]
            cmd = params.get("cmd", [""])[0]
            if not cmd:
                return {"error": "Missing cmd parameter"}
            if self.server_mgr and server in self.server_mgr.list_servers():
                try:
                    r = self.server_mgr.execute(server, cmd)
                    return {"output": r["stdout"], "exit_code": r["exit_code"]}
                except Exception as e:
                    return {"error": str(e)}
            return {"error": f"Server '{server}' not found"}
        return {"error": "Not found"}

    def start(self):
        api = self
        _api_key = self.api_key

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                api_key = self.headers.get("X-Api-Key", "")
                if not secrets.compare_digest(api_key, _api_key):
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
                    return
                result = api._handle(self)
                status = 200
                if isinstance(result, tuple):
                    status = result[1]
                    result = result[0]
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result, indent=2).encode())

            def log_message(self, format, *args):
                pass

        self._running = True
        server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return self.port

    def stop(self):
        self._running = False


# === 6. CONFIG PROFILES ===

class ProfileManager:
    def __init__(self, profiles_dir=None):
        self.dir = Path(profiles_dir or Path(__file__).parent.parent / ".profiles")
        self.dir.mkdir(parents=True, exist_ok=True)

    def list_profiles(self):
        return [f.stem for f in self.dir.glob("*.json")]

    def save_profile(self, name, config):
        (self.dir / f"{name}.json").write_text(json.dumps(config, indent=2))

    def load_profile(self, name):
        f = self.dir / f"{name}.json"
        if f.exists():
            return json.loads(f.read_text())
        return None

    def delete_profile(self, name):
        f = self.dir / f"{name}.json"
        if f.exists():
            f.unlink()
            return True
        return False


# === 7. SECURITY AUDIT ===

def audit_server(server_mgr, name):
    checks = []
    cmds = [
        ("SSH Root Login", "grep -i 'PermitRootLogin' /etc/ssh/sshd_config 2>/dev/null | grep -v '^#' | head -1"),
        ("Firewall Status", "ufw status 2>/dev/null || iptables -L -n 2>/dev/null | head -5 || echo 'No firewall found'"),
        ("Open Ports", "ss -tlnp 2>/dev/null | head -10 || netstat -tlnp 2>/dev/null | head -10"),
        ("Failed Logins", "lastb 2>/dev/null | wc -l || echo 'N/A'"),
        ("Users with Shell", "grep -v '/nologin\\|/false' /etc/passwd 2>/dev/null | wc -l"),
        ("Disk Encrypted", "lsblk -o NAME,FSTYPE,MOUNTPOINT 2>/dev/null | grep crypt || echo 'No LUKS found'"),
        ("Auto Updates", "systemctl is-enabled unattended-upgrades 2>/dev/null || echo 'Not configured'"),
        ("SSH Key Auth", "grep -i 'PubkeyAuthentication' /etc/ssh/sshd_config 2>/dev/null | grep -v '^#' | head -1"),
    ]
    for label, cmd in cmds:
        try:
            r = server_mgr.execute(name, cmd)
            output = r["stdout"].strip() if r["exit_code"] == 0 else "N/A"
            risk = "low"
            if "root" in output.lower() and "yes" in output.lower():
                risk = "high"
            elif "N/A" in output:
                risk = "unknown"
            checks.append({"check": label, "result": output[:100], "risk": risk})
        except Exception:
            checks.append({"check": label, "result": "Error", "risk": "unknown"})
    return checks


# === 8. QUICK SSH ===

def quick_ssh(host, user="root", port=22, key=None):
    cmd_parts = ["ssh"]
    if port != 22:
        cmd_parts.extend(["-p", str(port)])
    if key:
        cmd_parts.extend(["-i", key])
    cmd_parts.append(f"{user}@{host}")
    return " ".join(cmd_parts)


# === 9. COMMAND TEMPLATES ===

class TemplateManager:
    def __init__(self, templates_file=None):
        self.file = Path(templates_file or Path(__file__).parent.parent / ".templates.json")
        self._templates = self._load()

    def _load(self):
        if self.file.exists():
            try:
                return json.loads(self.file.read_text())
            except Exception:
                pass
        return {}

    def _save(self):
        self.file.write_text(json.dumps(self._templates, indent=2))

    def add(self, name, command, description=""):
        self._templates[name] = {"command": command, "description": description, "created": datetime.now().isoformat()}
        self._save()

    def get(self, name):
        return self._templates.get(name)

    def list_all(self):
        return self._templates

    def remove(self, name):
        if name in self._templates:
            del self._templates[name]
            self._save()
            return True
        return False

    def render(self, name, **kwargs):
        t = self._templates.get(name)
        if not t:
            return None
        cmd = t["command"]
        for k, v in kwargs.items():
            cmd = cmd.replace(f"{{{k}}}", str(v))
        return cmd


# === 10. NETWORK MAP ===

def generate_network_map(server_mgr, node_keys=None):
    nodes = []
    if server_mgr:
        for name in server_mgr.list_servers():
            info = server_mgr.get_server_info(name)
            nodes.append({
                "name": name, "type": "server",
                "host": info["host"], "user": info["user"],
                "status": info.get("status", "unknown"),
            })
    if node_keys:
        for name, info in node_keys.items():
            nodes.append({
                "name": name, "type": "node",
                "host": info["host"], "port": info.get("port", 9999),
                "status": "configured",
            })
    return nodes
