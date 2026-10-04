import json, os, subprocess, re
from datetime import datetime
from cloudmesh.core.ssh_util import run_ssh

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
        from cloudmesh.core.ssh_util import build_ssh_cmd
        ssh_cmd = build_ssh_cmd(host, user, key, cmd, extra_flags=[])
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


def _sources_file():
    return os.path.join(DATA_DIR, "logagg_sources.json")


def _load_sources():
    p = _sources_file()
    if os.path.exists(p):
        try:
            data = json.load(open(p))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            pass
    return []


def _save_sources(sources):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_sources_file(), "w") as f:
        json.dump(sources, f, indent=2)


def _parse_since(since):
    if not since:
        return None
    m = re.match(r"^\s*(\d+)\s*([smhd]?)\s*$", str(since).lower())
    if not m:
        return None
    num, unit = int(m.group(1)), m.group(2) or "h"
    return num * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _to_entries(server, log, text, level=None):
    entries = []
    for i, line in enumerate((text or "").splitlines()):
        line = line.strip()
        if not line:
            continue
        detected = "info"
        low = line.lower()
        if "error" in low or "fail" in low or "critical" in low:
            detected = "error"
        elif "warn" in low:
            detected = "warn"
        elif "debug" in low:
            detected = "debug"
        entries.append({
            "server": server, "log": log, "level": level or detected,
            "message": line, "index": i,
        })
    return entries


class LogAggregator:
    """Adapter exposing the CLI-facing log API over the functions above."""

    def add_source(self, server=None, path=None, tag="default"):
        if not path:
            return "Specify a log path with --path"
        sources = _load_sources()
        entry = {"tag": tag, "server": server or "all", "path": path}
        sources = [s for s in sources if s.get("tag") != tag]
        sources.append(entry)
        _save_sources(sources)
        return f"Source '{tag}' added ({entry['server']}:{path})"

    def list_sources(self):
        return _load_sources()

    def _resolve(self, source):
        """Resolve a source tag/name to [(server, path)]."""
        if source:
            for s in _load_sources():
                if s.get("tag") == source or s.get("server") == source:
                    return [(s.get("server"), s.get("path"))]
        if source:
            return [(source, "/var/log/syslog")]
        return [(None, "/var/log/syslog")]

    def search(self, pattern, source=None, since="1h", limit=50):
        try:
            limit = max(int(limit), 1)
        except (TypeError, ValueError):
            limit = 50
        out = []
        for server, path in self._resolve(source):
            if server in (None, "all"):
                for r in aggregate_logs([path], search=pattern, lines=limit):
                    out.extend(_to_entries(r["server"], r["log"], "\n".join(r["entries"])))
            else:
                text = get_logs(server, path, lines=limit, search=pattern)
                if isinstance(text, str) and "not found" not in text and "Failed" not in text:
                    out.extend(_to_entries(server, path, text))
        return out[:limit]

    def filter_logs(self, source=None, level="info", since="1h", limit=50):
        try:
            limit = max(int(limit), 1)
        except (TypeError, ValueError):
            limit = 50
        out = []
        for server, path in self._resolve(source):
            if server in (None, "all"):
                for r in aggregate_logs([path], lines=limit):
                    out.extend(_to_entries(r["server"], r["log"], "\n".join(r["entries"])))
            else:
                text = get_logs(server, path, lines=limit)
                if isinstance(text, str) and "not found" not in text and "Failed" not in text:
                    out.extend(_to_entries(server, path, text))
        want = (level or "info").lower()
        out = [e for e in out if e["level"] == want]
        return out[:limit]

    def subscribe(self, source=None, filter=None, interval=2):  # noqa: A002 - CLI flag name
        server, path = self._resolve(source)[0]
        if server in (None, "all"):
            return "Subscribe needs a concrete server: --source SERVER"
        text = follow_log(server, path)
        if filter:
            text = "\n".join(l for l in (text or "").splitlines() if filter.lower() in l.lower())
        return text or "(no output)"

    def stats(self):
        counts = {}
        total = 0
        for s in _load_sources():
            text = get_logs(s.get("server"), s.get("path"), lines=200)
            n = len((text or "").splitlines()) if isinstance(text, str) else 0
            counts[s.get("tag")] = n
            total += n
        lines = [f"{tag}: {n} line(s)" for tag, n in counts.items()]
        lines.append(f"total: {total} line(s)")
        return "\n".join(lines) if counts else "No log sources configured"

    def clear(self, source=None):
        if not source:
            _save_sources([])
            return "All log sources cleared"
        sources = [s for s in _load_sources() if s.get("tag") != source and s.get("server") != source]
        _save_sources(sources)
        return f"Source '{source}' cleared"
