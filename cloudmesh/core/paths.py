"""Shared filesystem locations for CloudMesh state.

``resolve_base_dir`` is the single switch for the database, encryption key, and
backups. Feature modules that predate it kept their JSON files beside the
installed package, which is read-only on a system install and is not moved by
``CLOUDMESH_DIR``. Resolve those paths through this module so a sandbox or a
per-user install relocates all state together.
"""

from __future__ import annotations

from pathlib import Path

try:
    from cloudmesh.core.storage import resolve_base_dir
except ImportError:  # pragma: no cover - source checkout without installed package
    from core.storage import resolve_base_dir


def base_dir() -> Path:
    return resolve_base_dir()


def data_dir() -> Path:
    return base_dir() / "data"


def state_file(name: str) -> Path:
    return base_dir() / name
