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
    """Run a command with no inherited stdin. Isolated for tests.

    Return a CompletedProcess with stdout and stderr captured as text, even
    for a nonzero exit status. Use cwd as the working directory when supplied;
    timeout is in seconds. Process startup errors, TimeoutExpired, and output
    decoding errors propagate to the caller.
    """
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
    Return False for a missing executable, a nonzero exit status, or an OS or
    subprocess error, including a 10-second timeout. Output decoding errors
    propagate.
    """
    if _which("git") is None:
        return False
    try:
        return _run(["git", "--version"]).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def git_version() -> str:
    """Return stripped stdout from git --version, or "" when unavailable.

    Return "" if the availability check fails or the subsequent version call
    raises an OS or subprocess error. That second call's exit status is not
    checked. Output decoding errors propagate.
    """
    if not git_available():
        return ""
    try:
        result = _run(["git", "--version"])
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def update_support(base_dir: Path | str | None = None) -> str:
    """Return how this installation can be updated: "git" or "pip".

    A source checkout is a git working tree, so it can pull when git is
    available. Everything else — a wheel install, or a checkout on a machine
    without git — can still be refreshed with
    `pip install --upgrade cloudmesh`, which is why "pip" is the floor and
    "none" is never returned. Inspect .git directly under base_dir, defaulting
    to this module's project root.
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
    base = Path(base_dir)
    if (base / ".git").exists() and git_available():
        return "git"
    return "pip"


def _installed_version() -> str:
    """Return the local version reported by get_version, including its fallback.

    Return "" if the version is empty or importing or calling get_version fails.
    """
    try:
        from cloudmesh.core.features import get_version

        return str(get_version().get("version") or "")
    except Exception:
        return ""


def installed_version(base_dir: Path | str | None = None) -> str:
    """Return the version of the CloudMesh this checkout provides.

    Read pyproject.toml under base_dir, defaulting to this module's project
    root. Prefer the first stripped line starting with "version" over the
    local get_version result. A missing file, no matching line, or an OSError
    while reading falls back to _installed_version, which may return "".
    Invalid UTF-8 raises UnicodeDecodeError; a matching line without "="
    raises IndexError.
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
    """Return the local version from _installed_version, or "" on lookup failure.

    This includes get_version's fallback and does not query remote releases.
    """
    return _installed_version()


def update_advice(base_dir: Path | str | None = None, tmp_path_with_git: bool = False) -> str:
    """Return a one-line status suitable for `cm doctor` and `cm update`.

    Names the installed version when it is known, says whether git is present,
    and states what that means for self-update. Pass base_dir to
    installed_version; its read/parse errors propagate. tmp_path_with_git is
    ignored. Advice depends on Git availability without checking for .git;
    Git output decoding errors propagate.
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