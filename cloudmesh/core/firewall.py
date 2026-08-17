import json, os, subprocess

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

def firewall_list(server_name):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    out, _ = _run_ssh(host, user, key, "which ufw 2>/dev/null")
    if "ufw" in out:
        status, _ = _run_ssh(host, user, key, "ufw status verbose")
        return status
    else:
        out, _ = _run_ssh(host, user, key, "iptables -L -n --line-numbers 2>/dev/null || echo 'No firewall found'")
        return out

def firewall_add_rule(server_name, rule):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    out, rc = _run_ssh(host, user, key, "which ufw 2>/dev/null")
    if "ufw" in out:
        out, rc = _run_ssh(host, user, key, f"ufw {rule}")
        return f"Rule added: {rule}" if rc == 0 else f"Failed: {out}"
    else:
        return "UFW not found. Install with: sudo apt install ufw"

def firewall_delete_rule(server_name, rule_num):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    out, rc = _run_ssh(host, user, key, "which ufw 2>/dev/null")
    if "ufw" in out:
        out, rc = _run_ssh(host, user, key, f"ufw delete {rule_num}")
        return f"Rule deleted" if rc == 0 else f"Failed: {out}"
    return "UFW not found"

def firewall_enable(server_name):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
    out, rc = _run_ssh(host, user, key, "ufw --force enable")
    return "Firewall enabled" if rc == 0 else f"Failed: {out}"

def firewall_disable(server_name):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
    out, rc = _run_ssh(host, user, key, "ufw disable")
    return "Firewall disabled" if rc == 0 else f"Failed: {out}"

def firewall_check_all():
    cfg = _load_config()
    results = []
    for section in ["servers", "nodes"]:
        for name, srv in cfg.get(section, {}).items():
            host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
            out, rc = _run_ssh(host, user, key, "ufw status 2>/dev/null | head -1 || echo 'not installed'")
            enabled = "active" in out.lower()
            results.append({"server": name, "status": out, "enabled": enabled})
    return results
