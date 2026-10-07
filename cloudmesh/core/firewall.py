import json, os
from cloudmesh.core.ssh_util import run_ssh

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

ALLOWED_RULES = {
    "allow", "deny", "reject",
    "allow 22/tcp", "allow 80/tcp", "allow 443/tcp", "allow 8080/tcp",
    "allow from", "deny from",
    "limit", "delete",
    "enable", "disable", "status",
    "reset", "default deny incoming", "default allow outgoing",
}


def _validate_rule(rule):
    parts = rule.strip().split()
    base = parts[0].lower() if parts else ""
    if base not in ("allow", "deny", "reject", "limit", "delete", "enable", "disable", "default"):
        return False, f"Unknown action: {base}"
    if base in ("allow", "deny", "reject", "limit"):
        if len(parts) < 2:
            return False, f"{base} requires a target (port/IP)"
        rule_str = rule.strip()
        if rule_str not in ALLOWED_RULES and not any(rule_str.startswith(p) for p in ("allow ", "deny ", "reject ", "limit ", "delete ")):
            return False, f"Rule not in allowlist: {rule_str}"
    return True, ""


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
    valid, msg = _validate_rule(rule)
    if not valid:
        return f"Invalid rule: {msg}"

    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    out, _ = _run_ssh(host, user, key, "which ufw 2>/dev/null")
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

    out, _ = _run_ssh(host, user, key, "which ufw 2>/dev/null")
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


def _parse_ufw_rules(status_output):
    """Parse `ufw status numbered` lines into rule dicts (best effort)."""
    import re
    rules = []
    for line in (status_output or "").splitlines():
        m = re.match(r"\s*\[\s*(\d+)\]\s+(\S+)\s+(ALLOW|DENY|REJECT|LIMIT)\s+(?:IN|OUT)\s+(\S+)",
                     line.strip(), re.I)
        if not m:
            continue
        _, port_proto, action, source = m.groups()
        if "/" in port_proto:
            port, proto = port_proto.split("/", 1)
        else:
            port, proto = port_proto, "tcp"
        v6 = "(v6)" in line
        rules.append({
            "port": port, "protocol": proto.lower(), "action": action.lower(),
            "source": ("*" if source.lower() in ("anywhere",) else source) + (" (v6)" if v6 else ""),
        })
    return rules


class FirewallManager:
    """Adapter exposing the CLI-facing firewall API over the functions above."""

    def list_rules(self, server=None):
        """Return firewall rules for a server, or a summary across all servers."""
        if not server:
            results = firewall_check_all()
            rules = []
            for r in results:
                rules.append({"port": "?", "protocol": "?", "action": r.get("status", ""), "source": r.get("server", "")})
            return rules
        out = firewall_list(server)
        if not isinstance(out, str) or "not found" in out:
            return []
        rules = _parse_ufw_rules(out)
        if rules:
            return rules
        # Non-UFW output (e.g. iptables): expose raw text as a single row.
        text = out.strip()
        if not text or text == "No firewall found":
            return []
        return [{"port": "?", "protocol": "?", "action": "raw", "source": ""}]

    def add_rule(self, port, proto="tcp", action="allow", server=None):
        """Add a firewall rule for a port/protocol on the given server."""
        if server is None:
            return "Specify a server with --server"
        return firewall_add_rule(server, f"{action} {port}/{proto}")

    def remove_rule(self, port, proto="tcp", server=None):
        """Remove the allow rule for a port/protocol on the given server."""
        if server is None:
            return "Specify a server with --server"
        return firewall_delete_rule(server, f"allow {port}/{proto}")

    def status(self, server=None):
        """Return the firewall status for a server, or all servers if none given."""
        if server is None:
            results = firewall_check_all()
            if not results:
                return "No servers configured"
            return "\n".join(f"{r['server']}: {r['status']}" for r in results)
        return firewall_list(server)

    def check_port(self, port, server=None):
        """Check whether a port is open or closed on the given server."""
        if server is None:
            return "Specify a server with --server"
        srv = _get_server(server)
        if not srv:
            return f"Server '{server}' not found"
        out, rc = _run_ssh(srv.get("host"), srv.get("user", "root"), srv.get("key", ""),
                            f"ss -tln 2>/dev/null | grep -E ':{port} ' || echo 'closed'")
        state = "open" if "closed" not in out else "closed"
        return f"Port {port} on {server}: {state}"

    def backup(self, server=None, output="firewall_backup.json"):
        """Save the current firewall rules for a server to a JSON file."""
        import json as _json
        rules = self.list_rules(server)
        try:
            with open(output, "w") as f:
                _json.dump(rules, f, indent=2)
            return f"Backed up {len(rules)} rule(s) to {output}"
        except OSError as e:
            return f"Backup failed: {e}"

    def load_rules(self, path, server=None):
        """Load firewall rules from a JSON file and apply them to a server."""
        import json as _json
        if server is None:
            return "Specify a server with --server"
        try:
            with open(path) as f:
                data = _json.load(f)
        except (OSError, ValueError) as e:
            return f"Load failed: {e}"
        items = data if isinstance(data, list) else [data]
        applied, failed = 0, 0
        for item in items:
            if isinstance(item, dict):
                rule = f"{item.get('action', 'allow')} {item.get('port', '')}"
                if item.get("protocol"):
                    rule += f"/{item['protocol']}"
            else:
                rule = str(item)
            res = firewall_add_rule(server, rule)
            if res.startswith("Rule added"):
                applied += 1
            else:
                failed += 1
        return f"Applied {applied} rule(s), {failed} failed"
