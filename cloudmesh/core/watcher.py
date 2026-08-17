import json, os, subprocess, time

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

def _watchers_file():
    return os.path.join(DATA_DIR, "watchers.json")

def _load_watchers():
    p = _watchers_file()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"watchers": [], "alerts": []}

def _save_watchers(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_watchers_file(), "w") as f:
        json.dump(data, f, indent=2)

def add_watcher(name, process_name, server=None, alert_on="stop", threshold=0):
    data = _load_watchers()
    watcher = {
        "name": name,
        "process": process_name,
        "server": server,
        "alert_on": alert_on,
        "threshold": threshold,
        "enabled": True,
        "created": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    data["watchers"].append(watcher)
    _save_watchers(data)
    return f"Watcher '{name}' added for process '{process_name}'"

def remove_watcher(name):
    data = _load_watchers()
    data["watchers"] = [w for w in data["watchers"] if w.get("name") != name]
    _save_watchers(data)
    return f"Watcher '{name}' removed"

def list_watchers():
    data = _load_watchers()
    return data.get("watchers", [])

def check_process(server_name, process_name):
    srv = _get_server(server_name)
    if not srv:
        return {"server": server_name, "process": process_name, "running": False, "error": "Server not found"}
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
    out, rc = _run_ssh(host, user, key, f"pgrep -f '{process_name}' 2>/dev/null | wc -l")
    try:
        count = int(out.strip())
    except:
        count = 0
    return {"server": server_name, "process": process_name, "running": count > 0, "instances": count}

def check_all_watchers():
    data = _load_watchers()
    results = []
    for w in data.get("watchers", []):
        if not w.get("enabled", True):
            continue
        server = w.get("server")
        process = w.get("process")
        alert_on = w.get("alert_on", "stop")

        if server:
            status = check_process(server, process)
        else:
            cfg = _load_config()
            status = None
            for section in ["servers", "nodes"]:
                for name, srv in cfg.get(section, {}).items():
                    s = check_process(name, process)
                    if status is None:
                        status = {"results": []}
                    status["results"].append(s)

        triggered = False
        if alert_on == "stop" and status:
            if isinstance(status, dict) and not status.get("running"):
                triggered = True
        elif alert_on == "start" and status:
            if isinstance(status, dict) and status.get("running"):
                triggered = True

        if triggered:
            alert = {
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "watcher": w["name"],
                "process": process,
                "alert": f"Process '{process}' {alert_on} detected"
            }
            data["alerts"].append(alert)

        results.append({"watcher": w["name"], "status": status, "triggered": triggered})

    data["alerts"] = data["alerts"][-100:]
    _save_watchers(data)
    return results

def watcher_alerts(limit=20):
    data = _load_watchers()
    return data.get("alerts", [])[-limit:]
