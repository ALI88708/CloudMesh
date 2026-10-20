import shlex
from cloudmesh.core.ssh_util import run_ssh, run_ssh_with_stdin
from cloudmesh.core.server_config import get_server as _store_server
from cloudmesh.core.server_config import load_server_config


def _remote_result(operation, output, return_code):
    if return_code == 0:
        return output
    message = f"Database {operation} failed (exit code {return_code})"
    if output:
        message += f": {output}"
    return message


def _load_config():
    return load_server_config()


def _get_server(name):
    return _store_server(name)

def _mysql_value(value):
    text = str(value)
    return '"' + (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\0", "")
    ) + '"'


def _credential_file_setup(variable, template, content):
    """Return shell lines that create an unpredictable owner-only temp file."""
    temp_path = f"${{TMPDIR:-/tmp}}/{template}"
    return (
        f'{variable}=$(mktemp "{temp_path}") || exit 1\n'
        f"trap 'rm -f \"${variable}\"' EXIT HUP INT TERM\n"
        "umask 077\n"
        f"printf '%s' {shlex.quote(content)} > \"${variable}\" || exit 1\n"
        f'chmod 600 "${variable}" || exit 1\n'
    )


def _mysql_cmd(user, host, port, password, database, sql):
    my_cnf = (
        "[client]\n"
        f"user={_mysql_value(user)}\n"
        f"password={_mysql_value(password)}\n"
        f"host={_mysql_value(host)}\n"
        f"port={int(port)}\n"
    )
    if database:
        my_cnf += f"database={_mysql_value(database)}\n"
    setup = _credential_file_setup("remote_conf", "cm_my.XXXXXX", my_cnf)
    run = (
        f'mysql --defaults-extra-file="$remote_conf" '
        f"-e {shlex.quote(sql)} 2>/dev/null"
    )
    return f"{setup}{run}\nrc=$?; exit $rc"

def _pgpass_value(value):
    # PostgreSQL's .pgpass format has no escape for a line break. Drop control
    # line characters rather than let a credential inject a second entry.
    text = str(value).replace("\n", "").replace("\r", "").replace("\0", "")
    return text.replace("\\", "\\\\").replace(":", "\\:")


def _postgres_cmd(user, host, port, password, database, sql):
    pgpass = f"*:*:*:{_pgpass_value(user)}:{_pgpass_value(password)}"
    setup = _credential_file_setup("remote_pgpass", "cm_pgpass.XXXXXX", pgpass)
    db_flag = f"-d {shlex.quote(database)}" if database else ""
    run = (
        f'PGPASSFILE="$remote_pgpass" psql -U {shlex.quote(user)} '
        f"-h {shlex.quote(host)} -p {int(port)} {db_flag} "
        f"-c {shlex.quote(sql)} 2>/dev/null"
    )
    return f"{setup}{run}\nrc=$?; exit $rc"

def list_databases(server_name, db_type="mysql", host="127.0.0.1", port=None, user="root", password=""):  # nosec B107 -- empty-string default, not a hardcoded credential
    """List MySQL or PostgreSQL databases through a configured server's SSH host.

    `host`, `port`, `user`, and `password` address the database from the SSH
    host; a falsey port selects 3306 for mysql or 5432 for postgres. Return
    command output on success, or a diagnostic for an unknown server,
    unsupported type, or SSH/remote command failure. Configuration read and
    JSON decoding errors propagate.
    """
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
    return _remote_result("list", out, rc)

def db_status(server_name, db_type="mysql", host="127.0.0.1", port=None, user="root", password=""):  # nosec B107 -- empty-string default, not a hardcoded credential
    """Fetch database connection counts and uptime through a configured SSH host.

    `host`, `port`, `user`, and `password` address the database from that host;
    a falsey port selects 3306 for mysql or 5432 for postgres. MySQL also
    reports its Questions counter. Return command output or a diagnostic for
    an unknown server, unsupported type, or SSH/remote command failure.
    Configuration read and JSON decoding errors propagate.
    """
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
    return _remote_result("status", out, rc)

def db_query(server_name, query, db_type="mysql", database="mysql", host="127.0.0.1", port=None, user="root", password=""):  # nosec B107 -- empty-string default, not a hardcoded credential
    """Execute SQL through a configured SSH host and return output or a diagnostic.

    `host`, `port`, `user`, and `password` address the database from that host;
    a falsey port selects 3306 for mysql or 5432 for postgres. Only those two
    database types are supported. The query may modify the selected database.
    Unknown servers and SSH/remote command failures return diagnostics;
    configuration read and JSON decoding errors propagate.
    """
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
    return _remote_result("query", out, rc)

# `backup_path` is a remote destination directory that gets shlex.quote()d into
# the remote command, not a local temp file, and the password default is an empty
# string rather than a secret. Note the spaces around the comma: bandit's nosec
# regex uses a repeating group, so `B108,B107` silently records only B107.
def db_backup(server_name, database, backup_path="/tmp", db_type="mysql", host="127.0.0.1", port=None, user="root", password=""):  # nosec B108 , B107
    """Write a timestamped SQL dump on the configured server's SSH host.

    `backup_path` is an existing remote directory, not a local destination.
    `host`, `port`, `user`, and `password` address the database from that host;
    a falsey port selects 3306 for mysql or 5432 for postgres. Return a message
    containing the remote dump path on success, or a diagnostic for an unknown
    server, unsupported type, or SSH/remote command failure. A failed dump may
    leave a partial file. Configuration read and JSON decoding errors propagate.
    """
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    ssh_host, ssh_user, ssh_key = srv.get("host"), srv.get("user", "root"), srv.get("key", "")

    filename = f"{database}_backup_{__import__('time').strftime('%Y%m%d_%H%M%S')}.sql"

    if db_type == "mysql":
        p = int(port or 3306)
        my_cnf = (
            "[client]\n"
            f"user={_mysql_value(user)}\n"
            f"password={_mysql_value(password)}\n"
            f"host={_mysql_value(host)}\n"
            f"port={p}\n"
        )
        setup = _credential_file_setup("remote_conf", "cm_my.XXXXXX", my_cnf)
        run = (
            f'mysqldump --defaults-extra-file="$remote_conf" '
            f"{shlex.quote(database)} > "
            f"{shlex.quote(backup_path + '/' + filename)} 2>/dev/null"
        )
        cmd = f"{setup}{run}\nrc=$?; exit $rc"
    elif db_type == "postgres":
        p = int(port or 5432)
        pgpass = f"*:*:*:{_pgpass_value(user)}:{_pgpass_value(password)}"
        setup = _credential_file_setup("remote_pgpass", "cm_pgpass.XXXXXX", pgpass)
        run = (
            f'PGPASSFILE="$remote_pgpass" pg_dump -U {shlex.quote(user)} '
            f"-h {shlex.quote(host)} -p {p} {shlex.quote(database)} > "
            f"{shlex.quote(backup_path + '/' + filename)} 2>/dev/null"
        )
        cmd = f"{setup}{run}\nrc=$?; exit $rc"
    else:
        return f"Unsupported: {db_type}"

    out, rc = run_ssh(ssh_host, ssh_user, ssh_key, cmd)
    if rc == 0:
        return f"Backup saved: {backup_path}/{filename}"
    return f"Backup failed: {out}"

def db_check_all(db_type="mysql", host="127.0.0.1", port=None, user="root", password=""):  # nosec B107 -- empty-string default, not a hardcoded credential
    """Collect database status through each configured server and node's SSH host.

    Pass the same database connection settings to db_status for every entry.
    Return a list of dictionaries with `server`, `status`, and `details` (at
    most 200 characters). Status is unreachable for empty output or a remote
    status failure, and ok otherwise, including unsupported-type diagnostics.
    Return an empty list if none are configured. Configuration read and JSON
    decoding errors propagate.
    """
    cfg = _load_config()
    results = []
    for section in ["servers", "nodes"]:
        for name, srv in cfg.get(section, {}).items():
            status = db_status(name, db_type, host, port, user, password)
            failed = status.startswith("Database status failed (exit code ")
            results.append({
                "server": name,
                "status": "unreachable" if failed or not status else "ok",
                "details": status[:200] if status else "",
            })
    return results
