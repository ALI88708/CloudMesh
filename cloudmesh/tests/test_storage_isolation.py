"""CLOUDMESH_DIR relocates storage, for both users and tests.

Defaulting to the package directory meant every storage-touching command wrote
to the installed package on a developer's machine. That is not merely untidy: it
is why the command harness could only run 80 of the 286 paths, because `cm panic`
would have rotated a real key and `cm uninstall` would have deleted a real
install.

The variable is a supported setting rather than a test hook, so it gets the same
edge-case treatment as any user-facing one: a nested path that does not exist yet
must simply work, and a path that cannot be created must fail legibly.
"""

import os
from pathlib import Path

import pytest

from cloudmesh.core import storage as storage_mod

PACKAGE_DIR = Path(storage_mod.__file__).parent.parent


def test_default_is_the_package_directory_when_unset(monkeypatch):
    monkeypatch.delenv("CLOUDMESH_DIR", raising=False)
    assert storage_mod.resolve_base_dir() == PACKAGE_DIR


def test_environment_variable_is_honoured(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    assert storage_mod.resolve_base_dir() == tmp_path


def test_explicit_argument_beats_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path / "from_env"))
    assert storage_mod.resolve_base_dir(tmp_path / "explicit") == tmp_path / "explicit"


def test_empty_variable_falls_back_to_the_package(monkeypatch):
    """An empty variable is a mistake, not a request to store in the CWD."""
    monkeypatch.setenv("CLOUDMESH_DIR", "")
    assert storage_mod.resolve_base_dir() == PACKAGE_DIR


def test_manager_uses_the_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    manager = storage_mod.StorageManager()
    assert manager.db_path == tmp_path / "cloudmesh.db"
    assert manager.key_path == tmp_path / ".secret.key"


def test_nested_missing_path_is_created_on_first_use(monkeypatch, tmp_path):
    """Someone setting the variable for the first time expects it to just work."""
    target = tmp_path / "deep" / "nested" / "base"
    monkeypatch.setenv("CLOUDMESH_DIR", str(target))
    storage_mod.StorageManager()
    assert target.is_dir()


def test_uncreatable_path_fails_with_a_clear_message(monkeypatch, tmp_path):
    """A path that cannot be used must say so, not raise something opaque."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("i am a file")
    monkeypatch.setenv("CLOUDMESH_DIR", str(blocker / "under"))
    with pytest.raises(OSError):
        storage_mod.StorageManager()


@pytest.mark.skipif(os.name != "nt", reason="POSIX collapses the trailing separator")
def test_windows_style_path_normalises(monkeypatch, tmp_path):
    spaced = tmp_path / "with space"
    spaced.mkdir()
    monkeypatch.setenv("CLOUDMESH_DIR", str(spaced) + "\\")
    assert storage_mod.resolve_base_dir() == spaced


def test_security_manager_follows_the_variable(monkeypatch, tmp_path):
    """`SecurityManager` holds the same secrets as the database.

    It resolves its own base directory inline, so a sandboxed `CLOUDMESH_DIR`
    moved the database but left the config and the key behind in the package
    directory. The harness then read state the developer's real install had
    written, which is the silent-corruption failure the variable exists to stop.
    """
    from cloudmesh.core import security as security_mod

    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    manager = security_mod.SecurityManager()
    assert manager.base_dir == tmp_path
    assert manager.config_path == tmp_path / "config.json"
    assert manager.key_path == tmp_path / ".secret.key"


def test_config_written_by_one_manager_is_read_by_the_next(monkeypatch, tmp_path):
    """A write that does not survive a fresh manager is not a write."""
    from cloudmesh.core import security as security_mod

    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    security_mod.SecurityManager().save_config({"servers": {"s": {"password": "x"}}})
    assert security_mod.SecurityManager().load_config()["servers"]["s"]["password"] == "x"


def test_security_manager_creates_a_nested_variable_path(monkeypatch, tmp_path):
    """A first-time nested path must just work here too, not only for the database."""
    from cloudmesh.core import security as security_mod

    target = tmp_path / "deep" / "nested" / "base"
    monkeypatch.setenv("CLOUDMESH_DIR", str(target))
    security_mod.SecurityManager()
    assert (target / "backups").is_dir()


def test_security_manager_explicit_argument_still_wins(monkeypatch, tmp_path):
    """The precedence contract is `explicit`, then the variable, then the package."""
    from cloudmesh.core import security as security_mod

    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path / "from_env"))
    manager = security_mod.SecurityManager(base_dir=tmp_path / "explicit")
    assert manager.base_dir == tmp_path / "explicit"


def _run_doctor(monkeypatch, capsys):
    """Call `cm doctor` wide enough that a path is not truncated.

    `doctor` renders a rich table, and at the default width a long path is
    folded and replaced with an ellipsis. Asserting on a path that the renderer
    cut in half would test rich's layout, not the row -- so COLUMNS is widened
    and the assertion stays exact.
    """
    import main as main_mod

    monkeypatch.setenv("COLUMNS", "300")
    main_mod.cmd_doctor(type("A", (), {"base_dir": None, "as_json": False})())
    return capsys.readouterr().out


def test_doctor_reports_the_data_directory(monkeypatch, tmp_path, capsys):
    """A wrong `CLOUDMESH_DIR` silently relocates a user's data.

    Every other row in `doctor` is the code inspecting itself, so a user with a
    bad setting sees a green table while their database, key, and config have
    quietly moved somewhere they did not choose. This row is the only one that
    can show them that.
    """
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    out = _run_doctor(monkeypatch, capsys)
    assert "Data directory" in out
    assert str(tmp_path) in out


def test_doctor_row_names_the_source_of_the_data_directory(monkeypatch, tmp_path, capsys):
    """The row must say *why* the path is what it is, or a typo is unreadable."""
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path))
    assert "CLOUDMESH_DIR" in _run_doctor(monkeypatch, capsys)


def test_doctor_labels_the_package_default_when_the_variable_is_unset(monkeypatch, capsys):
    """Without the variable the row must not imply one is in play."""
    monkeypatch.delenv("CLOUDMESH_DIR", raising=False)
    out = _run_doctor(monkeypatch, capsys)
    assert "package default" in out
    assert str(PACKAGE_DIR) in out


def test_doctor_flags_a_data_directory_that_does_not_exist(monkeypatch, tmp_path, capsys):
    """A typo in the setting must show as a failing row, not a silent path.

    `is_dir()` is what turns this into a visible problem: without it the row
    would report the configured path as healthy while every command failed.
    """
    monkeypatch.setenv("CLOUDMESH_DIR", str(tmp_path / "never-created"))
    out = _run_doctor(monkeypatch, capsys)
    data_row = next(line for line in out.splitlines() if "Data directory" in line)
    assert "FAIL" in data_row, f"a missing data directory must not report healthy: {data_row}"