"""Git availability and update-path detection.

`cm update` is git-based: it shells out to `git fetch`, `git rev-list`, and
`git pull`. Two gaps motivated this module:

- Nothing ever checked for git. A user could install CloudMesh, see `cm update`
  advertised in the README, and only discover git was missing at the moment they
  tried to update.
- When git was missing, `subprocess.run` raised `FileNotFoundError` and the raw
  errno reached the terminal: "Update failed: [Errno 2] No such file or
  directory: 'git'".

Everything here answers rather than raises. A missing or broken git is a normal
state, not an exception, because every caller wants to report it and carry on.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

__all__ = [
    "git_available",
    "git_version",
    "update_support",
    "installed_version",
    "latest_version",
    "update_advice",
]

# Seconds. A `git --version` that has not answered by now is not usable.
_VERSION_TIMEOUT = 10


def _which(name: str) -> str | None:
    """Return the path to an executable, or None. Isolated for tests."""
    return shutil.which(name)


def _run(argv: list[str], cwd: str | Path | None = None, timeout: int = _VERSION_TIMEOUT):
    """Run a command with no inherited stdin. Isolated for tests."""
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
    )


def git_available() -> bool:
    """Return True when a git executable exists and actually runs.

    Presence on PATH is not enough: a shim that cannot execute would make
    `cm update` fail later with a stranger error than we can give here.
    """
    if _which("git") is None:
        return False
    try:
        return _run(["git", "--version"]).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def git_version() -> str:
    """Return the installed git version string, or "" when unavailable."""
    if not git_available():
        return ""
    try:
        result = _run(["git", "--version"])
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def update_support(base_dir: Path | str | None = None) -> str:
    """Return how this installation can be updated: "git", "pip", or "none".

    A source checkout is a git working tree, so it can pull. A wheel install has
    no .git, so only pip can refresh it. A checkout on a machine without git
    still has pip.
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
    base = Path(base_dir)
    if (base / ".git").exists():
        return "git" if git_available() else "pip"
    return "none"


def _installed_version() -> str:
    """Return the version of the currently importable cloudmesh package."""
    try:
        from cloudmesh.core.features import get_version

        return str(get_version().get("version") or "")
    except Exception:
        return ""


def installed_version(base_dir: Path | str | None = None) -> str:
    """Return the version of the CloudMesh this checkout provides.

    Prefers the checkout's own pyproject.toml over installed package metadata,
    so a developer running from source sees the version they are editing rather
    than whatever is in site-packages.
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
    pyproject = Path(base_dir) / "pyproject.toml"
    if pyproject.exists():
        try:
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("version"):
                    return stripped.split("=", 1)[1].strip().strip('"\'')
        except OSError:
            pass
    return _installed_version()


def latest_version() -> str:
    """Return the newest version available, or "" when it cannot be determined.

    Intentionally does not shell out to git: the useful comparison for an
    already-installed tool is "what is installed", and a failed lookup must
    leave the caller in charge of the message.
    """
    return _installed_version()


def update_advice(base_dir: Path | str | None = None, tmp_path_with_git: bool = False) -> str:
    """Return a one-line status suitable for `cm doctor` and `cm update`.

    Names the installed version when it is known, says whether git is present,
    and states what that means for self-update.
    """
    del tmp_path_with_git  # accepted for call-site clarity; git state comes from _which
    version = installed_version(base_dir)
    shown = version or "unknown"
    if git_available():
        return f"CloudMesh {shown} - git {git_version() or 'available'}; cm update can pull"
    return (
        f"CloudMesh {shown} - git not found; "
        "`cm update` needs git, or use `pip install --upgrade cloudmesh`"
    )