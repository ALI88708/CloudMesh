import json, os, time
from core.ssh_util import run_ssh

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
    return run_ssh(host, user, key, cmd)

def _history_file():
    return os.path.join(DATA_DIR, "resource_history.json")

def _load_history():
    p = _history_file()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}

def _save_history(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_history_file(), "w") as f:
        json.dump(data, f, indent=2)

def snapshot(server_name=None):
    cfg = _load_config()
    history = _load_history()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    targets = []
    if server_name:
        srv = _get_server(server_name)
        if srv:
            targets = [(server_name, srv)]
    else:
        for section in ["servers", "nodes"]:
            for name, srv in cfg.get(section, {}).items():
                targets.append((name, srv))

    for name, srv in targets:
        host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
        cmd = "echo $(top -bn1 | grep 'Cpu(s)' | awk '{print $2}')|$(free -m | awk '/Mem/{printf \"%.1f\", $3/$2*100}')|$(df -h / | awk 'NR==2{print $5}')"
        out, rc = _run_ssh(host, user, key, cmd)
        if rc == 0 and "|" in out:
            parts = out.split("|")
            cpu = float(parts[0]) if parts[0] else 0
            ram = float(parts[1]) if parts[1] else 0
            disk = int(parts[2].replace("%", "")) if parts[2] else 0

            if name not in history:
                history[name] = []
            history[name].append({
                "time": timestamp,
                "cpu": cpu,
                "ram": ram,
                "disk": disk
            })
            history[name] = history[name][-1000:]

    _save_history(history)
    return f"Snapshot saved at {timestamp}"

def show_history(server_name, metric=None, limit=20):
    history = _load_history()
    if server_name not in history:
        return f"No history for {server_name}"

    entries = history[server_name][-limit:]
    return entries

def summary(server_name):
    history = _load_history()
    if server_name not in history:
        return {"server": server_name, "error": "No data"}

    entries = history[server_name]
    if not entries:
        return {"server": server_name, "error": "No data"}

    cpus = [e["cpu"] for e in entries]
    rams = [e["ram"] for e in entries]
    disks = [e["disk"] for e in entries]

    return {
        "server": server_name,
        "samples": len(entries),
        "first": entries[0]["time"],
        "last": entries[-1]["time"],
        "cpu": {"min": min(cpus), "max": max(cpus), "avg": sum(cpus) / len(cpus)},
        "ram": {"min": min(rams), "max": max(rams), "avg": sum(rams) / len(rams)},
        "disk": {"min": min(disks), "max": max(disks), "latest": disks[-1]}
    }

def clear_history(server_name=None):
    history = _load_history()
    if server_name:
        history.pop(server_name, None)
    else:
        history = {}
    _save_history(history)
    return "History cleared"
