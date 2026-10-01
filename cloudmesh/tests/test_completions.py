import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import cmd_completions


@pytest.mark.parametrize("shell", ["bash", "zsh", "powershell"])
def test_completions_include_missing_top_level_command_and_queue_actions(
    shell, tmp_path
):
    output = tmp_path / f"completions.{shell}"
    cmd_completions(argparse.Namespace(shell=shell, output=str(output)))
    script = output.read_text(encoding="utf-8")

    assert b"\r" not in output.read_bytes()
    assert "watch" in script
    assert "worker" in script
    assert "min-cpu-free" in script
    assert "--once" in script


def test_zsh_completion_uses_command_position_for_nested_actions(tmp_path):
    output = tmp_path / "completions.zsh"
    cmd_completions(argparse.Namespace(shell="zsh", output=str(output)))
    script = output.read_text(encoding="utf-8")

    assert "for ((i=2; i<CURRENT; i++)); do" in script
    assert '"queue worker")' in script
    assert "node job start" in script


def test_powershell_completion_maps_subcommands_and_options(tmp_path):
    output = tmp_path / "completions.ps1"
    cmd_completions(argparse.Namespace(shell="powershell", output=str(output)))
    script = output.read_text(encoding="utf-8")

    assert 'Register-ArgumentCompleter -Native -CommandName cm, cloudmesh' in script
    assert '"queue" = @("submit", "status", "list", "cancel", "worker")' in script
    assert '"queue worker" = @("--interval", "-i", "--once", "--help", "-h")' in script
    assert "$context = $candidate" in script


@pytest.mark.skipif(shutil.which("bash") is None, reason="Bash is not installed")
def test_bash_completion_returns_nested_commands_and_matching_options(tmp_path):
    output = tmp_path / "completions.bash"
    cmd_completions(argparse.Namespace(shell="bash", output=str(output)))
    script = output.read_text(encoding="utf-8")
    checks = r'''
COMP_WORDS=(cm queue ""); COMP_CWORD=2
_cloudmesh_completions
printf 'queue:%s\n' "${COMPREPLY[*]}"
COMP_WORDS=(cm queue worker --i); COMP_CWORD=3
_cloudmesh_completions
printf 'worker-options:%s\n' "${COMPREPLY[*]}"
'''
    result = subprocess.run(
        ["bash"],
        input=output.read_bytes() + checks.encode("utf-8"),
        capture_output=True,
        check=True,
    )

    assert b"queue:submit status list cancel worker" in result.stdout
    assert b"worker-options:--interval" in result.stdout
