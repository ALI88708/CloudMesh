import shlex
from cloudmesh.core.ssh_util import run_ssh
from cloudmesh.core.server_config import get_server as _store_server
from cloudmesh.core.server_config import load_server_config

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
    return load_server_config()


def _get_server(name):
    return _store_server(name)

def _run_ssh(host, user, key, cmd):
    return run_ssh(host, user, key, cmd)

def _detect_backend(host, user, key):
    out, _ = _run_ssh(host, user, key, "which ufw 2>/dev/null")
    if "ufw" in out:
        return "ufw"
    out, _ = _run_ssh(host, user, key, "pfctl -s info 2>/dev/null")
    if out.strip():
        return "pf"
    out, _ = _run_ssh(host, user, key, "ipfw list 2>/dev/null")
    if out.strip():
        return "ipfw"
    out, _ = _run_ssh(host, user, key, "iptables -L -n 2>/dev/null")
    if out.strip():
        return "iptables"
    return "none"

def _pf_rules(host, user, key):
    out, _ = _run_ssh(host, user, key, "pfctl -a cloudmesh -sr 2>/dev/null")
    return [line.strip() for line in (out or "").splitlines() if line.strip()]

def _pf_apply(host, user, key, rules):
    payload = "".join(f"{rule}\n" for rule in rules)
    cmd = f"printf %s {shlex.quote(payload)} | pfctl -a cloudmesh -f -"
    _, rc = _run_ssh(host, user, key, cmd)
    return rc

def _pf_add_rule(host, user, key, rule):
    rule = rule.strip()
    rules = _pf_rules(host, user, key)
    if rule not in rules:
        rules.append(rule)
    rc = _pf_apply(host, user, key, rules)
    return f"Rule added: {rule}" if rc == 0 else "Failed: pfctl rejected the rule set"

def _pf_delete_rule(host, user, key, rule):
    rule = rule.strip()
    rules = _pf_rules(host, user, key)
    remaining = [existing for existing in rules if existing != rule]
    if len(remaining) == len(rules):
        return f"Rule not found: {rule}"
    rc = _pf_apply(host, user, key, remaining)
    return "Rule deleted" if rc == 0 else "Failed: pfctl rejected the rule set"

def _to_pf_rule(rule):
    """Translate a ufw-style rule into pf syntax; None when it cannot be mapped."""
    parts = (rule or "").strip().split()
    if len(parts) < 2:
        return None
    action = {"allow": "pass", "deny": "block", "reject": "block", "limit": "pass"}.get(parts[0].lower())
    if action is None:
        return None
    target = parts[1:]
    if target[0] == "from":
        source = target[1] if len(target) > 1 else "any"
        return f"{action} in from {source} to any"
    port_proto = target[0]
    if "/" in port_proto:
        port, proto = port_proto.split("/", 1)
    else:
        port, proto = port_proto, "tcp"
    if not port.isdigit():
        return None
    return f"{action} in proto {proto} from any to any port {port}"

def firewall_list(server_name):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    backend = _detect_backend(host, user, key)
    if backend == "ufw":
        status, _ = _run_ssh(host, user, key, "ufw status verbose")
        return status
    if backend == "pf":
        rules = _pf_rules(host, user, key)
        return "\n".join(rules) if rules else "No firewall found"
    if backend == "ipfw":
        out, _ = _run_ssh(host, user, key, "ipfw list 2>/dev/null")
        return out if out.strip() else "No firewall found"
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

    backend = _detect_backend(host, user, key)
    if backend == "ufw":
        out, rc = _run_ssh(host, user, key, f"ufw {rule}")
        return f"Rule added: {rule}" if rc == 0 else f"Failed: {out}"
    if backend == "pf":
        pf_rule = _to_pf_rule(rule)
        if pf_rule is None:
            return f"Invalid rule for pf: {rule}"
        return _pf_add_rule(host, user, key, pf_rule)
    if backend == "ipfw":
        return "ipfw rule management is not supported yet; use pf"
    return "UFW not found. Install with: sudo apt install ufw"

def firewall_delete_rule(server_name, rule_num):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    backend = _detect_backend(host, user, key)
    if backend == "ufw":
        out, rc = _run_ssh(host, user, key, f"ufw delete {rule_num}")
        return f"Rule deleted" if rc == 0 else f"Failed: {out}"
    if backend == "pf":
        text = str(rule_num).strip()
        pf_rule = text if text.startswith(("pass ", "block ")) else _to_pf_rule(text)
        if pf_rule is None:
            return "Failed: rule must be a pf rule or an allow/deny rule"
        return _pf_delete_rule(host, user, key, pf_rule)
    if backend == "ipfw":
        return "ipfw rule management is not supported yet; use pf"
    return "UFW not found"

def firewall_enable(server_name):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
    cmd = "pfctl -e" if _detect_backend(host, user, key) == "pf" else "ufw --force enable"
    out, rc = _run_ssh(host, user, key, cmd)
    return "Firewall enabled" if rc == 0 else f"Failed: {out}"

def firewall_disable(server_name):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
    cmd = "pfctl -d" if _detect_backend(host, user, key) == "pf" else "ufw disable"
    out, rc = _run_ssh(host, user, key, cmd)
    return "Firewall disabled" if rc == 0 else f"Failed: {out}"

def firewall_check_all():
    cfg = _load_config()
    results = []
    for section in ["servers", "nodes"]:
        for name, srv in cfg.get(section, {}).items():
            host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
            backend = _detect_backend(host, user, key)
            if backend == "pf":
                out, _ = _run_ssh(host, user, key, "pfctl -s info 2>/dev/null | head -1")
            elif backend == "ipfw":
                out, _ = _run_ssh(host, user, key, "ipfw list 2>/dev/null | head -1")
            else:
                out, _ = _run_ssh(host, user, key, "ufw status 2>/dev/null | head -1 || echo 'not installed'")
            text = out.lower()
            enabled = "active" in text or "enabled" in text
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
        host, user, key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")
        backend = _detect_backend(host, user, key)
        if backend == "pf":
            rules = _pf_rules(host, user, key)
            is_open = any(f"port {port}" in rule for rule in rules)
        elif backend == "ipfw":
            rules_out, _ = _run_ssh(host, user, key, "ipfw list 2>/dev/null")
            is_open = any(port in line.split() for line in rules_out.splitlines())
        else:
            out, rc = _run_ssh(host, user, key, f"ss -tln 2>/dev/null | grep -E ':{port} ' || echo 'closed'")
            is_open = "closed" not in out
        state = "open" if is_open else "closed"
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
