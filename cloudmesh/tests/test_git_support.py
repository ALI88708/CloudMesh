"""Tests for git availability detection.

`cm update` is git-based: it runs `git fetch`, `git rev-list`, and `git pull`.
The installers never checked for git, so a user could install CloudMesh,
find `cm update` advertised in the README, and only then discover git was
missing and no one had warned them.
"""

import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloudmesh.core import git_support


# --- detection ----------------------------------------------------------


def test_git_is_available_on_this_machine():
    """CI installs git, so the real detection must succeed here."""
    assert git_support.git_available() is True


def test_git_version_is_reported_when_present():
    version = git_support.git_version()
    assert version, "expected a version string for an installed git"
    assert re.search(r"\d+\.\d+", version), f"no version number in {version!r}"


def test_missing_git_is_reported_not_raised(monkeypatch):
    """A missing git must be a clean answer, never an exception.

    This is the shape of the bug: subprocess.run raises FileNotFoundError when
    the executable is absent, and `cm update` leaked that errno straight to the
    user.
    """
    monkeypatch.setattr(git_support, "_which", lambda _name: None)

    assert git_support.git_available() is False
    assert git_support.git_version() == ""


def test_detection_survives_a_git_that_cannot_execute(monkeypatch):
    """A shim on PATH that cannot run must not take the caller down.

    Presence on PATH proves nothing: a wrapper that exits non-zero, or one the
    OS refuses to start, would otherwise surface later as an unexplained update
    failure.
    """
    monkeypatch.setattr(git_support, "_which", lambda _name: "/usr/bin/git")
    monkeypatch.setattr(
        git_support, "_run", lambda *a, **k: _Completed(returncode=127)
    )

    assert git_support.git_available() is False


def test_detection_survives_a_git_that_cannot_be_spawned(monkeypatch):
    monkeypatch.setattr(git_support, "_which", lambda _name: "/usr/bin/git")
    monkeypatch.setattr(
        git_support,
        "_run",
        lambda *a, **k: (_ for _ in ()).throw(OSError("cannot spawn")),
    )

    assert git_support.git_available() is False
    assert git_support.git_version() == ""


class _Completed:
    def __init__(self, returncode: int):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""


# --- update support -----------------------------------------------------


def test_update_support_is_reported_for_a_plain_pip_install(tmp_path, monkeypatch):
    """A wheel install has no .git, but pip can still refresh it."""
    base = tmp_path / "site-packages"
    base.mkdir()

    # Not "none": `pip install --upgrade cloudmesh` works there, and reporting
    # "none" made cm doctor's Update path row FAIL on every normal install.
    assert git_support.update_support(base) == "pip"


def test_update_support_is_pip_when_git_is_missing_entirely(tmp_path, monkeypatch):
    """No checkout and no git: pip is still the updater."""
    monkeypatch.setattr(git_support, "_which", lambda _name: None)
    base = tmp_path / "site-packages"
    base.mkdir()

    assert git_support.update_support(base) == "pip"


def test_update_support_is_git_for_a_checkout(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "cloudmesh").mkdir()

    assert git_support.update_support(tmp_path) == "git"


def test_update_support_is_pip_for_a_checkout_without_git(tmp_path, monkeypatch):
    """A git checkout with no git on PATH can still be refreshed with pip."""
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(git_support, "_which", lambda _name: None)

    assert git_support.update_support(tmp_path) == "pip"


def test_installed_checkout_reports_the_version_it_can_upgrade_to(tmp_path, monkeypatch):
    base = tmp_path / "repo"
    (base / ".git").mkdir(parents=True)
    (base / "cloudmesh").mkdir()

    # No pyproject.toml in this checkout, so it falls back to package metadata.
    monkeypatch.setattr(git_support, "_installed_version", lambda: "3.4.0")

    assert git_support.installed_version(base) == "3.4.0"


def test_checkout_version_prefers_its_own_pyproject(tmp_path, monkeypatch):
    """A developer running from source must see the version they are editing."""
    base = tmp_path / "repo"
    base.mkdir()
    (base / "pyproject.toml").write_text('[project]\nversion = "9.9.9"\n', encoding="utf-8")
    monkeypatch.setattr(git_support, "_installed_version", lambda: "3.4.0")

    assert git_support.installed_version(base) == "9.9.9"


def test_latest_version_reads_the_installed_package_metadata(monkeypatch):
    """Must not shell out to git; the answer is 'what is installed'."""
    monkeypatch.setattr(
        git_support,
        "_run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not shell out")),
    )
    monkeypatch.setattr(git_support, "_installed_version", lambda: "3.4.0")

    assert git_support.latest_version() == "3.4.0"


def test_latest_version_returns_empty_when_metadata_is_missing(monkeypatch):
    monkeypatch.setattr(git_support, "_installed_version", lambda: "")

    assert git_support.latest_version() == ""


# --- update advice ------------------------------------------------------


def test_advice_names_git_when_it_is_missing(monkeypatch):
    """The whole point: tell the user what is missing and what it costs them."""
    monkeypatch.setattr(git_support, "_which", lambda _name: None)
    monkeypatch.setattr(git_support, "_installed_version", lambda: "3.4.0")

    message = git_support.update_advice(tmp_path_with_git=False)

    assert "Git" in message or "git" in message
    assert "3.4.0" in message


def test_advice_confirms_a_working_setup(monkeypatch):
    monkeypatch.setattr(git_support, "_which", lambda _name: "/usr/bin/git")
    monkeypatch.setattr(git_support, "_installed_version", lambda: "3.4.0")

    message = git_support.update_advice(tmp_path_with_git=True)

    assert "3.4.0" in message
    assert "not found" not in message.lower()


def test_advice_handles_missing_git_and_missing_version(monkeypatch):
    monkeypatch.setattr(git_support, "_which", lambda _name: None)
    monkeypatch.setattr(git_support, "_installed_version", lambda: "")

    message = git_support.update_advice(tmp_path_with_git=False)

    assert isinstance(message, str) and message


# --- installer contracts ------------------------------------------------

ROOT_DIR = ROOT.parent
LINUX_INSTALLER = ROOT_DIR / "cm_for-linux.sh"
WINDOWS_INSTALLER = ROOT_DIR / "cm_for-windows.bat"


def _installer_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


@pytest.mark.parametrize(
    "path", [LINUX_INSTALLER, WINDOWS_INSTALLER], ids=["linux", "windows"]
)
def test_installer_checks_for_git(path):
    """Neither installer mentions git today; both must check and offer it."""
    text = _installer_text(path)
    assert "git" in text.lower(), f"{path.name} never mentions git"
    assert "command -v git" in text or "where git" in text, (
        f"{path.name} does not detect git"
    )


@pytest.mark.parametrize(
    "path", [LINUX_INSTALLER, WINDOWS_INSTALLER], ids=["linux", "windows"]
)
def test_installer_non_interactive_mode_skips_the_git_prompt(path):
    """CI cannot answer a prompt, so --yes / /Y must not block on one."""
    text = _installer_text(path)
    assert "NONINTERACTIVE" in text


def test_windows_git_detection_is_not_inverted():
    """`if not !ERRORLEVEL! NEQ 0` means ERRORLEVEL == 0.

    Which is the *opposite* of what the branch names claim: git being present
    took the :git_missing path, and git being absent printed "Git found". CI
    never caught it because /Y skips the prompt entirely, so only interactive
    users would have hit it.
    """
    text = _installer_text(WINDOWS_INSTALLER)
    assert "if not !ERRORLEVEL! NEQ 0 goto :git_missing" not in text, (
        "inverted git detection: a successful `where git` would report git missing"
    )
    assert "if !ERRORLEVEL! NEQ 0 goto :git_missing" in text


def test_linux_git_detection_is_not_inverted():
    """`command -v git` returning success must take the found path."""
    text = _installer_text(LINUX_INSTALLER)
    assert "if !ERRORLEVEL! NEQ 0" not in text
    # The Linux check is a direct `command -v`, not an errorlevel test.
    assert "if command -v git > /dev/null 2>&1; then" in text


def test_doctor_reports_git_availability():
    """`cm doctor` is where a user looks for 'is my machine set up'."""
    import main as cloudmesh_main

    source = Path(cloudmesh_main.__file__).read_text(encoding="utf-8")
    assert "git_support" in source, "cmd_doctor does not use git_support"
    assert "Git" in source, "cmd_doctor has no git row"


# --- cm update routing --------------------------------------------------


class _UpdateArgs:
    def __init__(self, yes=False, git=False, pip=False):
        self.yes = yes
        self.git = git
        self.pip = pip


def test_update_without_git_explains_instead_of_leaking_errno(monkeypatch, capsys):
    """This was the reported symptom: a raw [Errno 2] reaching the terminal."""
    import main as cloudmesh_main

    monkeypatch.setattr(
        cloudmesh_main.git_support, "git_available", lambda: False
    )
    monkeypatch.setattr(cloudmesh_main.git_support, "git_version", lambda: "")
    monkeypatch.setattr(Path, "exists", _always_true)

    cloudmesh_main.cmd_update(_UpdateArgs())

    out = capsys.readouterr().out
    assert "Errno" not in out, f"raw errno leaked: {out}"
    assert "not installed" in out.lower()
    assert "--pip" in out


def test_update_git_flag_fails_loudly_when_git_is_missing(monkeypatch, capsys):
    """--git means 'I insist', so a missing git is an error, not advice."""
    import main as cloudmesh_main

    monkeypatch.setattr(
        cloudmesh_main.git_support, "git_available", lambda: False
    )
    monkeypatch.setattr(Path, "exists", _always_true)

    with pytest.raises(SystemExit) as exc:
        cloudmesh_main.cmd_update(_UpdateArgs(git=True))

    assert exc.value.code == 1
    assert "git-scm.com" in capsys.readouterr().out


def test_update_outside_a_checkout_points_at_pip(monkeypatch, capsys):
    """A wheel install has no .git, so git was never an option there."""
    import main as cloudmesh_main

    monkeypatch.setattr(Path, "exists", lambda self: False)

    cloudmesh_main.cmd_update(_UpdateArgs())

    out = capsys.readouterr().out
    assert "pip install --upgrade cloudmesh" in out


def test_update_pip_flag_works_even_outside_a_checkout(monkeypatch, capsys):
    """The regression: --pip was handled after the not-a-checkout early return.

    For a wheel install — the case where pip is the only updater — `cm update
    --pip` returned at the .git check before ever reaching the pip branch.
    """
    import main as cloudmesh_main

    called = []
    monkeypatch.setattr(
        cloudmesh_main, "cmd_update_via_pip", lambda: called.append(True)
    )
    monkeypatch.setattr(Path, "exists", lambda self: False)

    cloudmesh_main.cmd_update(_UpdateArgs(pip=True))

    assert called == [True], "cm update --pip never reached the pip updater"


def test_update_pip_flag_never_touches_git(monkeypatch, capsys):
    import main as cloudmesh_main

    called = []
    monkeypatch.setattr(
        cloudmesh_main, "cmd_update_via_pip", lambda: called.append(True)
    )
    monkeypatch.setattr(Path, "exists", _always_true)

    cloudmesh_main.cmd_update(_UpdateArgs(pip=True))

    assert called == [True]
    assert "fetch" not in capsys.readouterr().out


def test_update_help_offers_both_paths():
    """`cm update --git` was the whole ask; both flags must be discoverable."""
    import argparse

    import main as cloudmesh_main

    monkeypatch_argv = ["cloudmesh", "update", "--help"]
    saved = sys.argv
    sys.argv = monkeypatch_argv
    try:
        with pytest.raises(SystemExit):
            cloudmesh_main.main()
    finally:
        sys.argv = saved

    # Re-parse to inspect the flags directly.
    del argparse  # only imported to keep the import list honest
    source = Path(cloudmesh_main.__file__).read_text(encoding="utf-8")
    assert '"--git"' in source and '"--pip"' in source


def _always_true(self):
    """Make Path.exists() report a git checkout, whatever the path."""
    return str(self).endswith(".git") or Path.exists(self)


@pytest.mark.parametrize(
    "error",
    [FileNotFoundError("git disappeared"), PermissionError("not executable"),
     subprocess.TimeoutExpired("git", 10), subprocess.SubprocessError("failed")],
    ids=["missing", "permission", "timeout", "subprocess-error"],
)
def test_git_probe_handles_execution_errors(monkeypatch, error):
    monkeypatch.setattr(git_support, "_which", Mock(return_value="/test/git"))
    run = Mock(side_effect=error)
    monkeypatch.setattr(git_support, "_run", run)

    assert git_support.git_available() is False
    assert git_support.git_version() == ""


def test_missing_git_does_not_start_a_process(monkeypatch):
    monkeypatch.setattr(git_support, "_which", Mock(return_value=None))
    run = Mock(side_effect=AssertionError("must not start git"))
    monkeypatch.setattr(git_support, "_run", run)

    assert git_support.git_version() == ""
    run.assert_not_called()


@pytest.mark.parametrize("error", [OSError("removed"), subprocess.TimeoutExpired("git", 10)])
def test_git_version_handles_failure_after_successful_detection(monkeypatch, error):
    monkeypatch.setattr(git_support, "_which", Mock(return_value="/test/git"))
    monkeypatch.setattr(git_support, "_run", Mock(side_effect=[
        subprocess.CompletedProcess([], 0, stdout="git version 2.50.0\n"), error,
    ]))

    assert git_support.git_version() == ""


def test_git_version_strips_surrounding_whitespace(monkeypatch):
    monkeypatch.setattr(git_support, "git_available", Mock(return_value=True))
    monkeypatch.setattr(git_support, "_run", Mock(return_value=
        subprocess.CompletedProcess([], 0, stdout="  git version 2.50.0.windows.1\r\n")))

    assert git_support.git_version() == "git version 2.50.0.windows.1"


@pytest.mark.parametrize("with_cwd", [False, True])
def test_git_subprocess_is_bounded_and_has_no_inherited_stdin(monkeypatch, tmp_path, with_cwd):
    result = subprocess.CompletedProcess([], 1, stdout="", stderr="failure")
    run = Mock(return_value=result)
    monkeypatch.setattr(git_support.subprocess, "run", run)
    cwd = tmp_path if with_cwd else None

    assert git_support._run(["git", "--version"], cwd=cwd) is result
    run.assert_called_once_with(
        ["git", "--version"], cwd=str(tmp_path) if with_cwd else None,
        capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL,
    )


@pytest.mark.parametrize("available, expected", [(True, "git"), (False, "pip")])
def test_update_support_accepts_git_worktree_files(monkeypatch, tmp_path, available, expected):
    (tmp_path / ".git").write_text("gitdir: /some/repo/.git/worktrees/test\n")
    monkeypatch.setattr(git_support, "git_available", Mock(return_value=available))

    assert git_support.update_support(str(tmp_path)) == expected


def test_wheel_update_support_does_not_probe_git(monkeypatch, tmp_path):
    probe = Mock(side_effect=AssertionError("wheel installs cannot use git"))
    monkeypatch.setattr(git_support, "git_available", probe)

    assert git_support.update_support(tmp_path) == "none"
    probe.assert_not_called()


@pytest.mark.parametrize("version_line", ['version = "9.8.7"', "  version = '9.8.7'  "])
def test_checkout_version_accepts_quotes_and_whitespace(monkeypatch, tmp_path, version_line):
    (tmp_path / "pyproject.toml").write_text(f"[project]\n{version_line}\n", encoding="utf-8")
    fallback = Mock(return_value="1.0.0")
    monkeypatch.setattr(git_support, "_installed_version", fallback)

    assert git_support.installed_version(str(tmp_path)) == "9.8.7"
    fallback.assert_not_called()


@pytest.mark.parametrize("state", ["missing", "no-version", "unreadable"])
def test_checkout_version_falls_back_when_unavailable(monkeypatch, tmp_path, state):
    project = tmp_path / "pyproject.toml"
    if state == "no-version":
        project.write_text('[project]\nname = "cloudmesh"\n')
    elif state == "unreadable":
        project.mkdir()  # Opening a directory as a file raises OSError on supported platforms.
    fallback = Mock(return_value="7.6.5")
    monkeypatch.setattr(git_support, "_installed_version", fallback)

    assert git_support.installed_version(tmp_path) == "7.6.5"
    fallback.assert_called_once_with()


@pytest.mark.parametrize("metadata, expected", [
    ({"version": "7.6.5"}, "7.6.5"), ({"version": None}, ""), ({}, ""),
])
def test_package_version_handles_missing_metadata(monkeypatch, metadata, expected):
    from cloudmesh.core import features

    monkeypatch.setattr(features, "get_version", Mock(return_value=metadata))
    assert git_support._installed_version() == expected


def test_package_version_lookup_failure_is_reported_as_unknown(monkeypatch):
    from cloudmesh.core import features

    monkeypatch.setattr(features, "get_version", Mock(side_effect=RuntimeError("metadata missing")))
    assert git_support.latest_version() == ""


@pytest.mark.parametrize("available, version, git_version, expected", [
    (False, "", "", ["CloudMesh unknown", "git not found", "pip install --upgrade cloudmesh"]),
    (True, "9.8.7", "git version 2.50.0", ["CloudMesh 9.8.7", "2.50.0", "cm update can pull"]),
    (True, "9.8.7", "", ["CloudMesh 9.8.7", "git available", "cm update can pull"]),
])
def test_update_advice_explains_version_and_update_path(
    monkeypatch, tmp_path, available, version, git_version, expected,
):
    installed = Mock(return_value=version)
    monkeypatch.setattr(git_support, "installed_version", installed)
    monkeypatch.setattr(git_support, "git_available", Mock(return_value=available))
    monkeypatch.setattr(git_support, "git_version", Mock(return_value=git_version))

    message = git_support.update_advice(tmp_path)

    installed.assert_called_once_with(tmp_path)
    for fragment in expected:
        assert fragment in message
