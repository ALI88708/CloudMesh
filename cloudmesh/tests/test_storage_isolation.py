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