import json, os, subprocess, signal, time

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def _tunnels_file():
    return os.path.join(DATA_DIR, "tunnels.json")

def _load_tunnels():
    p = _tunnels_file()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"tunnels": [], "active": []}

def _save_tunnels(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_tunnels_file(), "w") as f:
        json.dump(data, f, indent=2)

def list_tunnels():
    data = _load_tunnels()
    return data.get("tunnels", [])

def add_tunnel(name, host, user, local_port, remote_host, remote_port, key=None, ssh_port=22):
    data = _load_tunnels()
    tunnel = {
        "name": name,
        "host": host,
        "user": user,
        "local_port": local_port,
        "remote_host": remote_host,
        "remote_port": remote_port,
        "key": key,
        "ssh_port": ssh_port,
        "created": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    data["tunnels"].append(tunnel)
    _save_tunnels(data)
    return f"Tunnel '{name}' added"

def remove_tunnel(name):
    data = _load_tunnels()
    stop_tunnel(name)
    data["tunnels"] = [t for t in data["tunnels"] if t.get("name") != name]
    _save_tunnels(data)
    return f"Tunnel '{name}' removed"

def start_tunnel(name):
    data = _load_tunnels()
    tunnel = None
    for t in data.get("tunnels", []):
        if t["name"] == name:
            tunnel = t
            break
    if not tunnel:
        return f"Tunnel '{name}' not found"

    for a in data.get("active", []):
        if a.get("name") == name:
            return f"Tunnel '{name}' is already running"

    ssh_cmd = ["ssh", "-f", "-N", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
    ssh_cmd += ["-L", f"{tunnel['local_port']}:{tunnel['remote_host']}:{tunnel['remote_port']}"]
    if tunnel.get("key"):
        ssh_cmd += ["-i", tunnel["key"]]
    ssh_cmd += ["-p", str(tunnel.get("ssh_port", 22))]
    ssh_cmd += [f"{tunnel['user']}@{tunnel['host']}"]

    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
        active = data.get("active", [])
        active.append({
            "name": name,
            "pid": result.pid if hasattr(result, "pid") else None,
            "started": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        data["active"] = active
        _save_tunnels(data)
        return f"Tunnel '{name}' started: localhost:{tunnel['local_port']} -> {tunnel['remote_host']}:{tunnel['remote_port']}"
    except Exception as e:
        return f"Failed to start tunnel: {e}"

def stop_tunnel(name):
    data = _load_tunnels()
    active = data.get("active", [])
    for a in active:
        if a.get("name") == name and a.get("pid"):
            try:
                os.kill(a["pid"], signal.SIGTERM)
            except:
                pass
    data["active"] = [a for a in active if a.get("name") != name]
    _save_tunnels(data)
    return f"Tunnel '{name}' stopped"

def stop_all_tunnels():
    data = _load_tunnels()
    for a in data.get("active", []):
        if a.get("pid"):
            try:
                os.kill(a["pid"], signal.SIGTERM)
            except:
                pass
    data["active"] = []
    _save_tunnels(data)
    return "All tunnels stopped"

def tunnel_status():
    data = _load_tunnels()
    return {
        "total": len(data.get("tunnels", [])),
        "active": data.get("active", []),
        "inactive": [t for t in data.get("tunnels", []) if t["name"] not in [a["name"] for a in data.get("active", [])]]
    }

def quick_tunnel(host, user, local_port, remote_port, key=None):
    name = f"quick-{host}-{remote_port}"
    add_tunnel(name, host, user, local_port, "127.0.0.1", remote_port, key)
    return start_tunnel(name)
