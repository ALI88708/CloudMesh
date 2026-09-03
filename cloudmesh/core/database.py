import json, os, shlex, tempfile
from core.ssh_util import run_ssh, run_ssh_with_stdin

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

def _mysql_cmd(user, host, port, password, database, sql):
    my_cnf = f"[client]\nuser={user}\npassword={password}\nhost={host}\nport={port}\n"
    if database:
        my_cnf += f"database={database}\n"
    remote_conf = "/tmp/.cm_my.conf"
    create = f"printf '%s' {shlex.quote(my_cnf)} > {remote_conf} && chmod 600 {remote_conf}"
    run = f"mysql --defaults-extra-file={remote_conf} -e {shlex.quote(sql)} 2>/dev/null"
    cleanup = f"rm -f {remote_conf}"
    return f"{create} && {run}; rc=$?; {cleanup}; exit $rc"

def _postgres_cmd(user, host, port, password, database, sql):
    pgpass = shlex.quote(f"*:*:*:{user}:{password}")
    remote_pgpass = "/tmp/.cm_pgpass"
    create = f"printf '%s' {pgpass} > {remote_pgpass} && chmod 600 {remote_pgpass}"
    db_flag = f"-d {shlex.quote(database)}" if database else ""
    run = f"PGPASSFILE={remote_pgpass} psql -U {user} -h {host} -p {port} {db_flag} -c {shlex.quote(sql)} 2>/dev/null"
    cleanup = f"rm -f {remote_pgpass}"
    return f"{create} && {run}; rc=$?; {cleanup}; exit $rc"

def list_databases(server_name, db_type="mysql", host="127.0.0.1", port=None, user="root", password=""):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    ssh_host, ssh_user, ssh_key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    if db_type == "mysql":
        p = port or 3306
        cmd = _mysql_cmd(user, host, p, password, None, "SHOW DATABASES;")
    elif db_type == "postgres":
        p = port or 5432
        cmd = _postgres_cmd(user, host, p, password, None, "\\l")
    else:
        return f"Unsupported database type: {db_type}"

    out, rc = run_ssh(ssh_host, ssh_user, ssh_key, cmd)
    return out

def db_status(server_name, db_type="mysql", host="127.0.0.1", port=None, user="root", password=""):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    ssh_host, ssh_user, ssh_key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    if db_type == "mysql":
        p = port or 3306
        sql = "SHOW STATUS LIKE 'Threads_connected'; SHOW STATUS LIKE 'Uptime'; SHOW STATUS LIKE 'Questions';"
        cmd = _mysql_cmd(user, host, p, password, None, sql)
    elif db_type == "postgres":
        p = port or 5432
        sql = "SELECT count(*) as connections FROM pg_stat_activity; SELECT now() - pg_postmaster_start_time() as uptime;"
        cmd = _postgres_cmd(user, host, p, password, None, sql)
    else:
        return f"Unsupported: {db_type}"

    out, rc = run_ssh(ssh_host, ssh_user, ssh_key, cmd)
    return out

def db_query(server_name, query, db_type="mysql", database="mysql", host="127.0.0.1", port=None, user="root", password=""):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    ssh_host, ssh_user, ssh_key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    if db_type == "mysql":
        p = port or 3306
        cmd = _mysql_cmd(user, host, p, password, database, query)
    elif db_type == "postgres":
        p = port or 5432
        cmd = _postgres_cmd(user, host, p, password, database, query)
    else:
        return f"Unsupported: {db_type}"

    out, rc = run_ssh(ssh_host, ssh_user, ssh_key, cmd)
    return out

def db_backup(server_name, database, backup_path="/tmp", db_type="mysql", host="127.0.0.1", port=None, user="root", password=""):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    ssh_host, ssh_user, ssh_key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    filename = f"{database}_backup_{__import__('time').strftime('%Y%m%d_%H%M%S')}.sql"

    if db_type == "mysql":
        p = port or 3306
        my_cnf = f"[client]\nuser={user}\npassword={password}\nhost={host}\nport={p}\n"
        remote_conf = "/tmp/.cm_my.conf"
        create = f"printf '%s' {shlex.quote(my_cnf)} > {remote_conf} && chmod 600 {remote_conf}"
        run = f"mysqldump --defaults-extra-file={remote_conf} {shlex.quote(database)} > {shlex.quote(backup_path + '/' + filename)} 2>/dev/null"
        cleanup = f"rm -f {remote_conf}"
        cmd = f"{create} && {run}; rc=$?; {cleanup}; exit $rc"
    elif db_type == "postgres":
        p = port or 5432
        pgpass = shlex.quote(f"*:*:*:{user}:{password}")
        remote_pgpass = "/tmp/.cm_pgpass"
        create = f"printf '%s' {pgpass} > {remote_pgpass} && chmod 600 {remote_pgpass}"
        run = f"PGPASSFILE={remote_pgpass} pg_dump -U {user} -h {host} -p {p} {shlex.quote(database)} > {shlex.quote(backup_path + '/' + filename)} 2>/dev/null"
        cleanup = f"rm -f {remote_pgpass}"
        cmd = f"{create} && {run}; rc=$?; {cleanup}; exit $rc"
    else:
        return f"Unsupported: {db_type}"

    out, rc = run_ssh(ssh_host, ssh_user, ssh_key, cmd)
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
