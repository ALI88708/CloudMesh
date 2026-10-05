import os
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime


def ping_all(server_mgr, node_keys=None):
    results = {}
    for name in server_mgr.list_servers():
        try:
            ok, msg = server_mgr.test_connection(name)
            results[name] = {"type": "server", "online": ok, "msg": msg}
        except Exception as e:
            results[name] = {"type": "server", "online": False, "msg": str(e)}
    if node_keys:
        from cloudmesh.core.node_client import NodeClient
        for name, info in node_keys.items():
            try:
                c = NodeClient.from_config(info)
                online = c.ping()
                results[name] = {"type": "node", "online": online, "msg": "OK" if online else "OFFLINE"}
            except Exception as e:
                results[name] = {"type": "node", "online": False, "msg": str(e)}
    return results


def get_uptime(server_mgr, name):
    try:
        r = server_mgr.execute(name, "uptime -p 2>/dev/null || uptime")
        return r["stdout"] if r["exit_code"] == 0 else "N/A"
    except Exception:
        return "N/A"


def get_top_processes(server_mgr, name, limit=5, sort_by="cpu"):
    flag = "-o %cpu" if sort_by == "cpu" else "-o %mem"
    cmd = f"ps {flag} --sort=-{'pcpu' if sort_by == 'cpu' else 'pmem'} --no-headers -A | head -n {limit}"
    try:
        r = server_mgr.execute(name, cmd)
        if r["exit_code"] == 0:
            procs = []
            for line in r["stdout"].strip().split("\n"):
                parts = line.split()
                if len(parts) >= 2:
                    procs.append({"pid": parts[0], "usage": parts[1], "name": " ".join(parts[2:])})
            return procs
        return []
    except Exception:
        return []


def get_disk_detail(server_mgr, name):
    cmd = "df -h --output=source,size,used,avail,pcent,target 2>/dev/null | grep -E '^/' || df -h 2>/dev/null | grep -E '^/'"
    try:
        r = server_mgr.execute(name, cmd)
        if r["exit_code"] != 0:
            return []
        disks = []
        for line in r["stdout"].strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 6:
                disks.append({"device": parts[0], "size": parts[1], "used": parts[2], "avail": parts[3], "use%": parts[4], "mount": parts[5]})
        return disks
    except Exception:
        return []


def get_network_info(server_mgr, name):
    cmd = "ip -4 addr show 2>/dev/null | grep -E 'inet ' || ipconfig 2>/dev/null"
    try:
        r = server_mgr.execute(name, cmd)
        return r["stdout"] if r["exit_code"] == 0 else "N/A"
    except Exception:
        return "N/A"


def get_logged_users(server_mgr, name):
    try:
        r = server_mgr.execute(name, "who 2>/dev/null || query user 2>/dev/null")
        return r["stdout"] if r["exit_code"] == 0 else "N/A"
    except Exception:
        return "N/A"


def search_files(server_mgr, name, path, pattern):
    cmd = f"find {path} -name '{pattern}' -type f 2>/dev/null | head -n 20"
    try:
        r = server_mgr.execute(name, cmd)
        return r["stdout"].strip().split("\n") if r["exit_code"] == 0 else []
    except Exception:
        return []


def get_recent_logs(server_mgr, name, log_file="/var/log/syslog", lines=20):
    cmd = f"tail -n {lines} {log_file} 2>/dev/null || tail -n {lines} /var/log/messages 2>/dev/null"
    try:
        r = server_mgr.execute(name, cmd)
        return r["stdout"] if r["exit_code"] == 0 else "N/A"
    except Exception:
        return "N/A"


def export_config(security, filepath):
    config = security.load_config()
    Path(filepath).write_text(json.dumps(config, indent=2))
    return True


def import_config(security, filepath):
    data = json.loads(Path(filepath).read_text())
    security.save_config(data)
    return True


def encrypt_file(filepath, key=None):
    from cryptography.fernet import Fernet
    if key is None:
        key = Fernet.generate_key()
    f = Fernet(key)
    data = Path(filepath).read_bytes()
    encrypted = f.encrypt(data)
    out = Path(filepath + ".encrypted")
    out.write_bytes(encrypted)
    return key, str(out)


def decrypt_file(filepath, key):
    from cryptography.fernet import Fernet
    f = Fernet(key)
    data = Path(filepath).read_bytes()
    decrypted = f.decrypt(data)
    out = Path(filepath.replace(".encrypted", ""))
    out.write_bytes(decrypted)
    return str(out)


def network_speed_test(server_mgr, name, target="8.8.8.8", count=3):
    cmd = f"ping -c {count} {target} 2>/dev/null"
    try:
        r = server_mgr.execute(name, cmd)
        if r["exit_code"] == 0:
            for line in r["stdout"].split("\n"):
                if "avg" in line or "mdev" in line:
                    return line.strip()
        return "N/A"
    except Exception:
        return "N/A"


def scan_subnet(subnet, port=9999, timeout=1):
    import socket
    found = []
    base = ".".join(subnet.split(".")[:3])
    for i in range(1, 255):
        ip = f"{base}.{i}"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            result = s.connect_ex((ip, port))
            if result == 0:
                found.append(ip)
            s.close()
        except Exception:
            pass
    return found


def cleanup_old(security, jobs_dir=None, max_age_days=7):
    removed = 0
    backups = security.list_backups()
    cutoff = time.time() - (max_age_days * 86400)
    for b in backups:
        try:
            if b.stat().st_mtime < cutoff:
                b.unlink()
                removed += 1
        except Exception:
            pass
    if jobs_dir:
        jd = Path(jobs_dir)
        if jd.exists():
            for f in jd.glob("*.json"):
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                        removed += 1
                except Exception:
                    pass
    return removed


def generate_report(server_mgr, monitor, node_keys=None):
    report = {"timestamp": datetime.now().isoformat(), "servers": {}, "nodes": {}}
    for name in server_mgr.list_servers():
        try:
            m = monitor.get_all_metrics(name)
            report["servers"][name] = m
        except Exception:
            report["servers"][name] = None
    if node_keys:
        from cloudmesh.core.node_client import NodeClient
        for name, info in node_keys.items():
            try:
                c = NodeClient.from_config(info)
                m = c.get_metrics()
                report["nodes"][name] = m
            except Exception:
                report["nodes"][name] = None
    return report


def _read_alias_mirror(f):
    """Read a name-to-command map, accepting strings or command dictionaries.

    Missing, unreadable, invalid, or non-object JSON yields an empty map.
    """
    aliases = {}
    if f.exists():
        try:
            data = json.loads(f.read_text())
            if isinstance(data, dict):
                for name, command in data.items():
                    if isinstance(command, dict):
                        command = command.get("command", "")
                    aliases[name] = str(command)
        except Exception:
            pass
    return aliases


def create_alias(name, command, aliases_file=None, storage=None):
    """Create or replace an alias and return True on completion.

    command may be a value converted to text or a dictionary containing
    command. With storage, attempt a marker-guarded JSON import and mirror
    the updated database; storage failures fall back to writing JSON alone.
    Mirror write errors are suppressed on the storage path, but file write
    errors from the JSON-only path propagate.
    """
    f = Path(aliases_file or Path(__file__).parent.parent / ".aliases.json")
    if isinstance(command, dict):
        command = command.get("command", "")
    command = str(command)
    if storage is not None:
        try:
            imported_clean = storage.legacy_imported("aliases")
            if not imported_clean:
                ok = True
                for aname, acmd in _read_alias_mirror(f).items():
                    try:
                        storage.upsert_alias(aname, acmd)
                    except Exception:
                        ok = False
                        continue
                if ok:
                    storage.mark_legacy_imported("aliases")
                    imported_clean = True
            storage.upsert_alias(name, command)
            if imported_clean:
                _push_alias_mirror(storage, f)
            else:
                # Import incomplete: merge only the new key so unimported
                # legacy rows in the JSON source are never clobbered.
                mirror = _read_alias_mirror(f)
                mirror[name] = command
                f.write_text(json.dumps(mirror, indent=2))
            return True
        except Exception:
            pass
    aliases = _read_alias_mirror(f)
    aliases[name] = command
    f.write_text(json.dumps(aliases, indent=2))
    return True


def _push_alias_mirror(storage, f):
    """Rewrite changed alias JSON from storage, suppressing read/write errors."""
    try:
        rows = storage.list_aliases()
    except Exception:
        return
    if rows != _read_alias_mirror(f):
        try:
            f.write_text(json.dumps(rows, indent=2))
        except Exception:
            pass


def get_aliases(aliases_file=None, storage=None):
    """Return aliases from storage, falling back to JSON when empty or failing.

    Supplying storage also attempts a marker-guarded legacy import.
    Missing or unreadable JSON yields an empty dictionary.
    """
    f = Path(aliases_file or Path(__file__).parent.parent / ".aliases.json")
    if storage is not None:
        try:
            if not storage.legacy_imported("aliases"):
                ok = True
                for aname, acmd in _read_alias_mirror(f).items():
                    try:
                        storage.upsert_alias(aname, acmd)
                    except Exception:
                        ok = False
                        continue
                if ok:
                    storage.mark_legacy_imported("aliases")
            rows = storage.list_aliases()
            return rows
        except Exception:
            pass
    return _read_alias_mirror(f)


def remove_alias(name, aliases_file=None, storage=None):
    """Remove an alias and return whether it was found before deletion.

    With storage, suppress database and mirror errors; True does not confirm
    a successful deletion. Without storage, JSON file write errors propagate.
    """
    f = Path(aliases_file or Path(__file__).parent.parent / ".aliases.json")
    if storage is not None:
        try:
            existed = name in storage.list_aliases()
        except Exception:
            existed = False
        try:
            storage.remove_alias(name)
        except Exception:
            pass
        _push_alias_mirror(storage, f)
        return existed
    aliases = get_aliases(aliases_file)
    if name in aliases:
        del aliases[name]
        f.write_text(json.dumps(aliases, indent=2))
        return True
    return False


def get_version():
    """Return package version, Python version, and platform information.

    Use 3.3.0 when installed package metadata cannot be read.
    """
    try:
        from importlib.metadata import version as _pkg_version
        try:
            ver = _pkg_version("cloudmesh")
        except Exception:
            ver = "3.4.0"
    except Exception:
        ver = "3.4.0"
    return {
        "version": ver,
        "python": f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}.{__import__('sys').version_info.micro}",
        "platform": __import__('sys').platform,
    }
