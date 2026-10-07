"""Isolated tests for the Git/pip update choices and doctor diagnostics."""

import io
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rich.console import Console

from cloudmesh import main


@pytest.fixture
def update_env(tmp_path, monkeypatch):
    package = tmp_path / "cloudmesh"
    package.mkdir()
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(main, "__file__", str(package / "main.py"))
    output = io.StringIO()
    monkeypatch.setattr(main, "console", Console(file=output, width=180, color_system=None))
    run = Mock(side_effect=AssertionError("unexpected subprocess"))
    monkeypatch.setattr(main.subprocess, "run", run)
    monkeypatch.setattr(main.git_support, "installed_version", Mock(return_value="3.4.0"))
    monkeypatch.setattr(main.git_support, "git_available", Mock(return_value=True))
    monkeypatch.setattr(main, "get_version", Mock(return_value={"version": "3.5.0"}))
    prompt = Mock(side_effect=AssertionError("unexpected prompt"))
    monkeypatch.setattr("rich.prompt.Confirm.ask", prompt)
    return SimpleNamespace(root=tmp_path, output=output, run=run, prompt=prompt)


def _args(**overrides):
    return SimpleNamespace(**{"yes": False, "git": False, "pip": False, **overrides})


@pytest.mark.parametrize("force_git", [False, True])
def test_missing_git_stops_before_fetch(update_env, monkeypatch, force_git):
    monkeypatch.setattr(main.git_support, "git_available", Mock(return_value=False))
    if force_git:
        with pytest.raises(SystemExit) as exc:
            main.cmd_update(_args(git=True))
        assert exc.value.code == 1
        assert "git-scm.com/downloads" in update_env.output.getvalue()
    else:
        main.cmd_update(_args())
        assert "cm update --pip" in update_env.output.getvalue()
    update_env.run.assert_not_called()
    update_env.prompt.assert_not_called()


@pytest.mark.parametrize("force_git", [False, True])
def test_explicit_pip_bypasses_git_detection_and_confirmation(update_env, monkeypatch, force_git):
    probe = Mock(side_effect=AssertionError("pip must not require Git"))
    monkeypatch.setattr(main.git_support, "git_available", probe)
    pip = Mock()
    monkeypatch.setattr(main, "cmd_update_via_pip", pip)

    main.cmd_update(_args(pip=True, git=force_git))

    pip.assert_called_once_with()
    probe.assert_not_called()
    update_env.run.assert_not_called()
    update_env.prompt.assert_not_called()


def test_explicit_pip_updates_a_wheel_install(update_env, monkeypatch):
    """A wheel has no .git directory but must still support --pip."""
    (update_env.root / ".git").rmdir()
    pip = Mock()
    monkeypatch.setattr(main, "cmd_update_via_pip", pip)

    main.cmd_update(_args(pip=True))

    pip.assert_called_once_with()
    update_env.run.assert_not_called()


def test_wheel_auto_update_gives_manual_instructions(update_env):
    (update_env.root / ".git").rmdir()

    main.cmd_update(_args())

    assert "pip install --upgrade cloudmesh" in update_env.output.getvalue()
    update_env.run.assert_not_called()


@pytest.mark.parametrize("force_git", [False, True])
def test_git_route_checks_checkout_without_prompt_when_current(update_env, force_git):
    update_env.run.side_effect = [
        subprocess.CompletedProcess([], 0, stdout=""),
        subprocess.CompletedProcess([], 0, stdout="0\n"),
    ]

    main.cmd_update(_args(git=force_git))

    calls = update_env.run.call_args_list
    assert [call.args[0] for call in calls] == [
        ["git", "fetch", "origin", "main"],
        ["git", "rev-list", "--count", "HEAD..origin/main"],
    ]
    assert all(call.kwargs["cwd"] == str(update_env.root) for call in calls)
    assert "Already up to date!" in update_env.output.getvalue()
    assert ("git (--git)" in update_env.output.getvalue()) is force_git
    update_env.prompt.assert_not_called()


@pytest.mark.parametrize("installed", ["3.4.0", ""])
def test_pip_upgrade_uses_active_python_and_reports_result(update_env, monkeypatch, installed):
    monkeypatch.setattr(main.git_support, "installed_version", Mock(return_value=installed))
    update_env.run.side_effect = None
    update_env.run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")

    main.cmd_update_via_pip()

    update_env.run.assert_called_once_with(
        [sys.executable, "-m", "pip", "install", "--upgrade", "cloudmesh"],
        capture_output=True, text=True, timeout=300,
    )
    assert f"Installed version: {installed or 'unknown'}" in update_env.output.getvalue()
    assert "Updated via pip to CloudMesh 3.5.0" in update_env.output.getvalue()
    update_env.prompt.assert_not_called()


def test_pip_failure_shows_only_tail_of_stderr(update_env, monkeypatch):
    version = Mock(side_effect=AssertionError("failed upgrade has no new version"))
    monkeypatch.setattr(main, "get_version", version)
    tail = "x" * 480 + " dependency conflict"
    update_env.run.side_effect = None
    update_env.run.return_value = subprocess.CompletedProcess(
        [], 1, stdout="", stderr="discard-this-prefix" + tail + "\n",
    )

    main.cmd_update_via_pip()

    output = update_env.output.getvalue().replace("\n", "")
    assert "pip upgrade failed:" in output
    assert tail in output
    assert "discard-this-prefix" not in output
    assert "Updated via pip" not in output
    version.assert_not_called()


@pytest.mark.parametrize("error", [
    OSError("cannot launch Python"), subprocess.TimeoutExpired("pip", 300),
])
def test_pip_execution_errors_are_reported_without_tracebacks(update_env, error):
    update_env.run.side_effect = error

    main.cmd_update_via_pip()

    assert "pip failed to start:" in update_env.output.getvalue()
    assert "Updated via pip" not in update_env.output.getvalue()
    assert "Traceback" not in update_env.output.getvalue()


@pytest.mark.parametrize("flags, expected", [
    ([], (False, False, False)), (["--git"], (True, False, False)),
    (["--pip", "-y"], (False, True, True)),
    (["--git", "--pip", "--yes"], (True, True, True)),
])
def test_update_parser_passes_flags_to_handler(monkeypatch, flags, expected):
    handler = Mock()
    monkeypatch.setattr(main, "cmd_update", handler)
    monkeypatch.setattr(sys, "argv", ["cm", "update", *flags])

    main.main()

    handler.assert_called_once()
    args = handler.call_args.args[0]
    assert (args.git, args.pip, args.yes) == expected


@pytest.fixture
def doctor_env(update_env, monkeypatch):
    # Keep unrelated storage diagnostics from initializing local databases or keys.
    from cloudmesh.core import storage

    monkeypatch.setattr(storage, "StorageManager", Mock(side_effect=RuntimeError("storage stub")))
    return update_env


def _doctor_row(output, label):
    rows = [line for line in output.splitlines() if line.strip().startswith(f"│ {label} ")]
    assert len(rows) == 1, output
    return rows[0]


@pytest.mark.parametrize("available, git_version, path, version", [
    (True, "git version 2.50.0", "git", "3.4.0"),
    (True, "", "none", ""),
    (False, "", "pip", "3.4.0"),
    (False, "", "none", ""),
])
def test_doctor_reports_git_and_update_path(doctor_env, monkeypatch, available, git_version, path, version):
    monkeypatch.setattr(main.git_support, "git_available", Mock(return_value=available))
    monkeypatch.setattr(main.git_support, "git_version", Mock(return_value=git_version))
    monkeypatch.setattr(main.git_support, "update_support", Mock(return_value=path))
    monkeypatch.setattr(main.git_support, "installed_version", Mock(return_value=version))

    main.cmd_doctor(SimpleNamespace(base_dir=doctor_env.root))

    output = doctor_env.output.getvalue()
    git_row = _doctor_row(output, "Git")
    assert ("PASS" if available else "FAIL") in git_row
    assert (git_version or "available" if available else "not found") in git_row
    update_row = _doctor_row(output, "Update path")
    assert ("FAIL" if path == "none" else "PASS") in update_row
    assert f"{path} ({version or 'version unknown'})" in update_row
    doctor_env.run.assert_not_called()


def test_doctor_continues_after_git_probe_error(doctor_env, monkeypatch):
    monkeypatch.setattr(main.git_support, "git_available", Mock(side_effect=RuntimeError("probe failed")))

    main.cmd_doctor(SimpleNamespace(base_dir=doctor_env.root))

    output = doctor_env.output.getvalue()
    row = _doctor_row(output, "Git")
    assert "FAIL" in row
    assert "check failed: probe failed" in row
    assert "Schedules" in output
    assert "Some checks failed" in output
