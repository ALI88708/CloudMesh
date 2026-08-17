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

def list_databases(server_name, db_type="mysql", host="127.0.0.1", port=None, user="root", password=""):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    ssh_host, ssh_user, ssh_key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    if db_type == "mysql":
        p = port or 3306
        cmd = f"mysql -u {user} -p'{password}' -h {host} -P {p} -e 'SHOW DATABASES;' 2>/dev/null"
    elif db_type == "postgres":
        p = port or 5432
        cmd = f"PGPASSWORD='{password}' psql -U {user} -h {host} -p {p} -c '\\l' 2>/dev/null"
    else:
        return f"Unsupported database type: {db_type}"

    out, rc = _run_ssh(ssh_host, ssh_user, ssh_key, cmd)
    return out

def db_status(server_name, db_type="mysql", host="127.0.0.1", port=None, user="root", password=""):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    ssh_host, ssh_user, ssh_key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    if db_type == "mysql":
        p = port or 3306
        cmd = f"mysql -u {user} -p'{password}' -h {host} -P {p} -e \"SHOW STATUS LIKE 'Threads_connected'; SHOW STATUS LIKE 'Uptime'; SHOW STATUS LIKE 'Questions';\" 2>/dev/null"
    elif db_type == "postgres":
        p = port or 5432
        cmd = f"PGPASSWORD='{password}' psql -U {user} -h {host} -p {p} -c \"SELECT count(*) as connections FROM pg_stat_activity; SELECT now() - pg_postmaster_start_time() as uptime;\" 2>/dev/null"
    else:
        return f"Unsupported: {db_type}"

    out, rc = _run_ssh(ssh_host, ssh_user, ssh_key, cmd)
    return out

def db_query(server_name, query, db_type="mysql", database="mysql", host="127.0.0.1", port=None, user="root", password=""):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    ssh_host, ssh_user, ssh_key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    safe_query = query.replace("'", "\\'").replace('"', '\\"')

    if db_type == "mysql":
        p = port or 3306
        cmd = f"mysql -u {user} -p'{password}' -h {host} -P {p} {database} -e \"{safe_query}\" 2>/dev/null"
    elif db_type == "postgres":
        p = port or 5432
        cmd = f"PGPASSWORD='{password}' psql -U {user} -h {host} -p {p} -d {database} -c \"{safe_query}\" 2>/dev/null"
    else:
        return f"Unsupported: {db_type}"

    out, rc = _run_ssh(ssh_host, ssh_user, ssh_key, cmd)
    return out

def db_backup(server_name, database, backup_path="/tmp", db_type="mysql", host="127.0.0.1", port=None, user="root", password=""):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    ssh_host, ssh_user, ssh_key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    filename = f"{database}_backup_{__import__('time').strftime('%Y%m%d_%H%M%S')}.sql"

    if db_type == "mysql":
        p = port or 3306
        cmd = f"mysqldump -u {user} -p'{password}' -h {host} -P {p} {database} > {backup_path}/{filename} 2>/dev/null"
    elif db_type == "postgres":
        p = port or 5432
        cmd = f"PGPASSWORD='{password}' pg_dump -U {user} -h {host} -p {p} {database} > {backup_path}/{filename} 2>/dev/null"
    else:
        return f"Unsupported: {db_type}"

    out, rc = _run_ssh(ssh_host, ssh_user, ssh_key, cmd)
    if rc == 0:
        return f"Backup saved: {backup_path}/{filename}"
    return f"Backup failed: {out}"

def db_check_all(db_type="mysql", host="127.0.0.1", port=None, user="root", password=""):
    cfg = _load_config()
    results = []
    for section in ["servers", "nodes"]:
        for name, srv in cfg.get(section, {}).items():
            status = db_status(name, db_type, host, port, user, password)
            results.append({"server": name, "status": "ok" if status else "unreachable", "details": status[:200] if status else ""})
    return results
