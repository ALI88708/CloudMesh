import json, os, subprocess

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def _plugins_dir():
    d = os.path.join(DATA_DIR, "plugins")
    os.makedirs(d, exist_ok=True)
    return d

def _plugins_index():
    p = os.path.join(DATA_DIR, "plugins.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}

def _save_index(idx):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "plugins.json"), "w") as f:
        json.dump(idx, f, indent=2)

def list_plugins():
    idx = _plugins_index()
    plugins = []
    for name, info in idx.items():
        plugins.append({
            "name": name,
            "description": info.get("description", ""),
            "command": info.get("command", ""),
            "targets": info.get("targets", "all")
        })
    return plugins

def add_plugin(name, command, description="", targets="all"):
    idx = _plugins_index()
    idx[name] = {
        "command": command,
        "description": description,
        "targets": targets
    }
    _save_index(idx)
    return f"Plugin '{name}' added"

def remove_plugin(name):
    idx = _plugins_index()
    if name in idx:
        del idx[name]
        _save_index(idx)
        return f"Plugin '{name}' removed"
    return f"Plugin '{name}' not found"

def run_plugin(name, server_name=None):
    idx = _plugins_index()
    if name not in idx:
        return f"Plugin '{name}' not found"

    plugin = idx[name]
    cmd = plugin["command"]
    targets = plugin.get("targets", "all")

    if targets == "local":
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            return result.stdout.strip()
        except Exception as e:
            return str(e)

    from core.server import load_servers
    servers = load_servers()
    results = {}

    if server_name:
        if server_name in servers:
            srv = servers[server_name]
            out = _run_remote(srv, cmd)
            results[server_name] = out
    else:
        for sname, srv in servers.items():
            out = _run_remote(srv, cmd)
            results[sname] = out

    return results

def _run_remote(srv, cmd):
    host = srv.get("host", "")
    user = srv.get("user", "root")
    key = srv.get("key", "")
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
    if key:
        ssh_cmd += ["-i", key]
    ssh_cmd += [f"{user}@{host}", cmd]
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=60)
        return result.stdout.strip()
    except Exception as e:
        return str(e)

def import_plugin(filepath):
    if not os.path.exists(filepath):
        return f"File not found: {filepath}"
    try:
        with open(filepath) as f:
            data = json.load(f)
        for name, info in data.items():
            add_plugin(name, info.get("command", ""), info.get("description", ""), info.get("targets", "all"))
        return f"Imported {len(data)} plugins"
    except Exception as e:
        return f"Import failed: {e}"

def export_plugin(name, filepath):
    idx = _plugins_index()
    if name not in idx:
        return f"Plugin '{name}' not found"
    data = {name: idx[name]}
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    return f"Exported to {filepath}"
