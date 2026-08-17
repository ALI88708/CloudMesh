import json, os, subprocess, re
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def _load_config():
    p = os.path.join(DATA_DIR, "cloudmesh.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}

def _get_server(name):
    cfg = _load_config()
    for section in ["servers", "nodes"]:
        if name in cfg.get(section, {}):
            return cfg[section][name]
    return None

def _run_ssh(host, user, key, cmd):
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
    if key:
        ssh_cmd += ["-i", key]
    ssh_cmd += [f"{user}@{host}", cmd]
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return str(e), 1

def get_logs(server_name, log_file="/var/log/syslog", lines=50, search=None, severity=None):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    cmd = f"tail -n {lines} {log_file} 2>/dev/null"
    if search:
        cmd = f"grep -i '{search}' {log_file} 2>/dev/null | tail -n {lines}"
    if severity:
        cmd = f"grep -i '{severity}' {log_file} 2>/dev/null | tail -n {lines}"

    out, rc = _run_ssh(host, user, key, cmd)
    return out if rc == 0 else f"Failed to read {log_file}"

def list_logs(server_name):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    out, _ = _run_ssh(host, user, key, "ls -lhS /var/log/*.log /var/log/syslog* /var/log/messages* 2>/dev/null | head -20")
    return out

def aggregate_logs(log_files=None, search=None, lines=100):
    cfg = _load_config()
    if not log_files:
        log_files = ["/var/log/syslog", "/var/log/auth.log"]

    results = []
    for section in ["servers", "nodes"]:
        for name, srv in cfg.get(section, {}).items():
            host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
            for lf in log_files:
                cmd = f"tail -n {lines} {lf} 2>/dev/null"
                if search:
                    cmd = f"grep -i '{search}' {lf} 2>/dev/null | tail -n {lines}"
                out, rc = _run_ssh(host, user, key, cmd)
                if out and rc == 0:
                    results.append({"server": name, "log": lf, "entries": out.split("\n")})
    return results

def follow_log(server_name, log_file="/var/log/syslog"):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
    cmd = f"tail -f {log_file} 2>/dev/null"
    try:
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no"]
        if key:
            ssh_cmd += ["-i", key]
        ssh_cmd += [f"{user}@{host}", cmd]
        proc = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines = []
        for _ in range(50):
            line = proc.stdout.readline()
            if line:
                lines.append(line.strip())
        proc.terminate()
        return "\n".join(lines)
    except Exception as e:
        return str(e)

def available_logs(server_name):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
    out, _ = _run_ssh(host, user, key, "ls /var/log/ 2>/dev/null")
    return out.split("\n") if out else []
