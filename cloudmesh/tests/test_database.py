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
