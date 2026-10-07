import json, os, subprocess, ssl, socket
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def _load_config():
    p = os.path.join(DATA_DIR, "cloudmesh.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}

def check_cert(domain, port=443):
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(10)
            s.connect((domain, port))
            cert = s.getpeercert()

        not_after = cert.get("notAfter", "")
        not_before = cert.get("notBefore", "")
        issuer = dict(x[0] for x in cert.get("issuer", []))
        subject = dict(x[0] for x in cert.get("subject", []))
        san = [e[1] for e in cert.get("subjectAltName", [])]

        expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
        issued = datetime.strptime(not_before, "%b %d %H:%M:%S %Y %Z")
        days_left = (expiry - datetime.now()).days

        return {
            "domain": domain,
            "status": "valid",
            "issuer": issuer.get("organizationName", "Unknown"),
            "subject": subject.get("commonName", domain),
            "san": san[:5],
            "not_before": not_before,
            "not_after": not_after,
            "days_left": days_left,
            "warning": days_left < 30,
            "critical": days_left < 7
        }
    except ssl.SSLCertVerificationError as e:
        return {"domain": domain, "status": "invalid", "error": str(e)}
    except Exception as e:
        return {"domain": domain, "status": "error", "error": str(e)}

def check_all_certs(domains):
    results = []
    for d in domains:
        if isinstance(d, dict):
            domain = d.get("domain", "")
            port = d.get("port", 443)
        else:
            domain = d
            port = 443
        results.append(check_cert(domain, port))
    return results

def load_domains():
    p = os.path.join(DATA_DIR, "ssl_domains.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return []

def save_domains(domains):
    os.makedirs(DATA_DIR, exist_ok=True)
    p = os.path.join(DATA_DIR, "ssl_domains.json")
    with open(p, "w") as f:
        json.dump(domains, f, indent=2)

def add_domain(domain, port=443):
    domains = load_domains()
    for d in domains:
        if d.get("domain") == domain:
            return f"{domain} already tracked"
    domains.append({"domain": domain, "port": port})
    save_domains(domains)
    return f"Added {domain}"

def remove_domain(domain):
    domains = load_domains()
    domains = [d for d in domains if d.get("domain") != domain]
    save_domains(domains)
    return f"Removed {domain}"

def check_all_tracked():
    return check_all_certs(load_domains())


class SSLChecker:
    """Adapter exposing the CLI-facing SSL API over the functions above."""

    def check_domain(self, domain, port=443):
        """Check the SSL certificate for a single domain."""
        return check_cert(domain, port)

    def check_all(self):
        """Check the SSL certificates for all tracked domains."""
        rows = []
        for r in check_all_tracked():
            if not isinstance(r, dict):
                continue
            rows.append({
                "domain": r.get("domain"),
                "valid": r.get("status") == "valid",
                "issuer": r.get("issuer", "?"),
                "expiry": r.get("not_after", "?"),
                "days_left": r.get("days_left", "?"),
            })
        return rows

    def list_domains(self):
        """Return the names of all tracked domains."""
        return [d.get("domain") for d in load_domains() if isinstance(d, dict) and d.get("domain")]

    def add_domain(self, domain, port=443):
        """Add a domain to the tracked list."""
        return add_domain(domain, port)

    def remove_domain(self, domain):
        """Remove a domain from the tracked list."""
        return remove_domain(domain)

    def history(self):
        """Return the current certificate status for all tracked domains, timestamped."""
        from datetime import datetime as _dt
        now = _dt.now().isoformat(timespec="seconds")
        rows = []
        for r in check_all_tracked():
            if not isinstance(r, dict):
                continue
            rows.append({
                "domain": r.get("domain"),
                "time": now,
                "valid": r.get("status") == "valid",
                "days_left": r.get("days_left"),
            })
        return rows

    def renew_check(self, days=30):
        """Return tracked domains whose certificates expire within the given number of days."""
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 30
        rows = [r for r in check_all_tracked() if isinstance(r, dict)]
        if not rows:
            return "No domains tracked. Add one: cm ssl add DOMAIN"
        urgent = [r for r in rows
                  if isinstance(r.get("days_left"), int) and r["days_left"] <= days]
        if not urgent:
            return f"All {len(rows)} domain(s) valid for more than {days} days"
        lines = [f"{r.get('domain')}: {r.get('days_left')} day(s) left" for r in urgent]
        return "Renewal needed:\n" + "\n".join(lines)
