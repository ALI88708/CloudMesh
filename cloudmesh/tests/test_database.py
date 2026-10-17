import json
import shlex
from unittest.mock import Mock, call

import pytest

from core import database


def _invoke(operation):
    if operation == "list":
        return database.list_databases("test")
    if operation == "status":
        return database.db_status("test")
    return database.db_query("test", "SELECT 1")


def _mock_server(monkeypatch):
    monkeypatch.setattr(
        database,
        "_get_server",
        lambda _name: {"host": "db-host", "user": "ssh-user", "key": "ssh-key"},
    )


@pytest.mark.parametrize("operation", ["list", "status", "query"])
@pytest.mark.parametrize(
    ("output", "return_code"),
    [("", 1), ("connection refused", 255)],
)
def test_database_operations_report_nonzero_remote_exit(
    monkeypatch, operation, output, return_code
):
    _mock_server(monkeypatch)
    monkeypatch.setattr(
        database, "run_ssh", lambda *_args: (output, return_code)
    )

    expected = f"Database {operation} failed (exit code {return_code})"
    if output:
        expected += f": {output}"
    assert _invoke(operation) == expected


@pytest.mark.parametrize("operation", ["list", "status", "query"])
def test_database_operations_preserve_successful_output(monkeypatch, operation):
    _mock_server(monkeypatch)
    monkeypatch.setattr(database, "run_ssh", lambda *_args: ("database output", 0))

    assert _invoke(operation) == "database output"


def test_database_check_all_marks_remote_status_failure_unreachable(monkeypatch):
    monkeypatch.setattr(database, "_load_config", lambda: {"servers": {"test": {}}})
    monkeypatch.setattr(
        database,
        "db_status",
        lambda *_args: "Database status failed (exit code 1): permission denied",
    )

    assert database.db_check_all() == [
        {
            "server": "test",
            "status": "unreachable",
            "details": "Database status failed (exit code 1): permission denied",
        }
    ]


@pytest.fixture(params=["list", "status", "query", "backup"])
def database_operation(request):
    operations = {
        "list": lambda **kwargs: database.list_databases("test", **kwargs),
        "status": lambda **kwargs: database.db_status("test", **kwargs),
        "query": lambda **kwargs: database.db_query("test", "SELECT '雪'", **kwargs),
        "backup": lambda **kwargs: database.db_backup(
            "test", "app data", backup_path="/srv/backups with spaces", **kwargs
        ),
    }
    return request.param, operations[request.param]


@pytest.mark.parametrize("engine", ["mysql", "postgres"])
@pytest.mark.parametrize("port", [None, 0, 6543], ids=["default", "falsey", "custom"])
def test_database_routes_through_ssh_with_separate_database_connection_settings(
    monkeypatch, database_operation, engine, port
):
    operation, invoke = database_operation
    _mock_server(monkeypatch)
    remote = Mock(return_value=("database output", 0))
    monkeypatch.setattr(database, "run_ssh", remote)

    result = invoke(
        db_type=engine, host="private-db", port=port,
        user="db-user", password="synthetic-secret",
    )

    remote.assert_called_once()
    ssh_host, ssh_user, ssh_key, command = remote.call_args.args
    assert (ssh_host, ssh_user, ssh_key) == ("db-host", "ssh-user", "ssh-key")
    expected_port = port or (3306 if engine == "mysql" else 5432)
    tokens = shlex.split(command)
    if engine == "mysql":
        assert "user=db-user\n" in tokens[2]
        assert "password=synthetic-secret\n" in tokens[2]
        assert "host=private-db\n" in tokens[2]
        assert f"port={expected_port}\n" in tokens[2]
    else:
        assert tokens[tokens.index("-U") + 1] == "db-user"
        assert tokens[tokens.index("-h") + 1] == "private-db"
        assert tokens[tokens.index("-p") + 1] == str(expected_port)
        assert "*:*:*:db-user:synthetic-secret" in tokens
    if operation == "backup":
        assert result.startswith("Backup saved: /srv/backups with spaces/app data_backup_")
        assert result.endswith(".sql")
        assert shlex.quote(result.removeprefix("Backup saved: ")) in command
        assert ("mysqldump" if engine == "mysql" else "pg_dump") in command
    else:
        assert result == "database output"
        if operation == "query":
            assert "SELECT '雪'" in tokens
            if engine == "mysql":
                assert "database=mysql\n" in tokens[2]
            else:
                assert tokens[tokens.index("-d") + 1] == "mysql"


def test_database_unknown_server_returns_diagnostic_without_ssh(
    monkeypatch, database_operation
):
    _, invoke = database_operation
    monkeypatch.setattr(database, "_get_server", Mock(return_value=None))
    remote = Mock()
    monkeypatch.setattr(database, "run_ssh", remote)

    assert invoke() == "Server 'test' not found"
    remote.assert_not_called()


def test_database_unsupported_type_returns_diagnostic_without_ssh(
    monkeypatch, database_operation
):
    operation, invoke = database_operation
    _mock_server(monkeypatch)
    remote = Mock()
    monkeypatch.setattr(database, "run_ssh", remote)

    prefix = "Unsupported database type" if operation == "list" else "Unsupported"
    assert invoke(db_type="sqlite") == f"{prefix}: sqlite"
    remote.assert_not_called()


@pytest.mark.parametrize("failure", ["io", "json"])
def test_database_configuration_errors_propagate_without_ssh(
    monkeypatch, database_operation, failure
):
    _, invoke = database_operation
    error = (
        PermissionError("config cannot be read") if failure == "io"
        else json.JSONDecodeError("invalid config", "{", 1)
    )
    monkeypatch.setattr(database, "_load_config", Mock(side_effect=error))
    remote = Mock()
    monkeypatch.setattr(database, "run_ssh", remote)

    with pytest.raises(type(error)) as exc:
        invoke()

    assert exc.value is error
    remote.assert_not_called()


@pytest.mark.parametrize("engine", ["mysql", "postgres"])
@pytest.mark.parametrize("output", ["", "disk full"])
def test_database_backup_failure_does_not_claim_a_saved_dump(monkeypatch, engine, output):
    _mock_server(monkeypatch)
    monkeypatch.setattr(database, "run_ssh", Mock(return_value=(output, 1)))

    assert database.db_backup("test", "app", db_type=engine) == f"Backup failed: {output}"


@pytest.mark.parametrize(
    ("output", "status"),
    [
        ("", "unreachable"),
        ("connections: 2", "ok"),
        ("Database status failed (exit code 255): offline", "unreachable"),
        ("Unsupported: sqlite", "ok"),
        ("雪" * 201, "ok"),
    ],
    ids=["empty", "healthy", "remote-failure", "diagnostic", "truncated"],
)
def test_database_check_all_includes_servers_and_nodes_and_bounds_details(
    monkeypatch, output, status
):
    monkeypatch.setattr(
        database, "_load_config",
        lambda: {"servers": {"server": {}}, "nodes": {"node": {}}},
    )
    check = Mock(return_value=output)
    monkeypatch.setattr(database, "db_status", check)

    results = database.db_check_all("postgres", "db-internal", 5433, "reader", "test-secret")

    assert results == [
        {"server": name, "status": status, "details": output[:200]}
        for name in ["server", "node"]
    ]
    assert check.call_args_list == [
        call(name, "postgres", "db-internal", 5433, "reader", "test-secret")
        for name in ["server", "node"]
    ]


def test_database_check_all_without_entries_does_not_probe(monkeypatch):
    monkeypatch.setattr(database, "_load_config", lambda: {})
    check = Mock()
    monkeypatch.setattr(database, "db_status", check)

    assert database.db_check_all() == []
    check.assert_not_called()
