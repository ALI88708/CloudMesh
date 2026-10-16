"""The numbers the README advertises must match what the code actually does.

These figures are hand-maintained, and nothing failed when they drifted: the
badge said 206 tests when the suite ran 826, and 155+ commands when the parser
exposed 286. Both were wrong for long enough that CI, which runs on every
push, never noticed -- because the badges are not built from anything.

So this file derives each advertised number from its source of truth and
compares. The version comes from `pyproject.toml`, the command count from the
real parser, and the test count from a collection-only run, which is cheap
because no test body executes.

Lives here rather than in `test_storage_isolation.py`, where the plan put it,
because this file is about release metadata and not about `CLOUDMESH_DIR`.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_pyproject_declares_the_released_version():
    """The single source of truth for the version number."""
    declared = re.search(r'^version\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.M)
    assert declared, "pyproject.toml has no version field"
    assert declared.group(1) == "3.5.2", f"pyproject says {declared.group(1)}"


def test_the_readme_version_badge_agrees_with_pyproject():
    """A badge is what a user reads first; a stale one misstates the release."""
    declared = re.search(r'^version\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.M).group(1)
    badge = re.search(r"Version-([0-9.]+)-", _read("README.md"))
    assert badge, "the README has no Version badge"
    assert badge.group(1) == declared, (
        f"the README badge says {badge.group(1)} but pyproject says {declared}"
    )


def test_the_changelog_documents_the_current_version():
    """A release without a changelog entry is a release nobody can audit."""
    assert re.search(r"^## \[3\.5\.2\]", _read("CHANGELOG.md"), re.M), (
        "CHANGELOG.md has no [3.5.2] section"
    )


def test_the_commands_badge_matches_the_real_parser():
    """The badge must be derived from the parser, not remembered."""
    import argparse
    import io
    from contextlib import redirect_stderr, redirect_stdout

    if str(ROOT / "cloudmesh") not in sys.path:
        sys.path.insert(0, str(ROOT / "cloudmesh"))
    import main as cloudmesh_main

    captured: dict = {}
    real = argparse.ArgumentParser.parse_args

    def spy(self, args=None, namespace=None):
        captured["parser"] = self
        raise SystemExit("__captured__")

    # Spying on parse_args aborts before dispatch, so nothing is executed and no
    # command can act. `cm panic` rotates every key; `cm storage restore`
    # overwrites the database.
    argparse.ArgumentParser.parse_args = spy
    saved_argv = sys.argv
    sys.argv = ["cloudmesh"]
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            cloudmesh_main.main()
    except SystemExit as exc:
        if exc.code != "__captured__":
            raise
    finally:
        argparse.ArgumentParser.parse_args = real
        sys.argv = saved_argv

    def subparsers(node):
        for action in node._actions:
            if isinstance(action, argparse._SubParsersAction):
                return action.choices
        return {}

    top = subparsers(captured["parser"])
    found: set[tuple[str, ...]] = set()
    queue = [[name] for name in top]
    while queue:
        path = queue.pop()
        key = tuple(path)
        if key in found:
            continue
        found.add(key)
        node = top[path[0]]
        for word in path[1:]:
            node = subparsers(node).get(word)
            if node is None:
                break
        else:
            for child in subparsers(node):
                queue.append([*path, child])

    badge = re.search(r"Commands-(\d+)", _read("README.md"))
    assert badge, "the README has no Commands badge"
    assert badge.group(1) == str(len(found)), (
        f"the README claims {badge.group(1)} commands; the parser exposes {len(found)}"
    )


def test_the_tests_badge_matches_the_real_suite():
    """The advertised test count is derived, so it cannot quietly rot again.

    Collection only: pytest is asked which tests exist rather than to run them,
    so this costs a parse of the suite instead of a full execution.

    The badge counts *collected* tests, not passing ones. The pass count varies
    by platform -- `test_windows_installer_extract.py` skips off Windows and the
    native-shell completion cases skip where the shell is missing -- so a static
    badge quoting "passed" would be wrong on at least one of the two OSes CI
    runs. The collected total is the same on both.
    """
    badge = re.search(r"Tests-(\d+)", _read("README.md"))
    assert badge, "the README has no Tests badge"

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header"],
        cwd=str(ROOT / "cloudmesh"),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, f"collection failed:\n{proc.stdout}\n{proc.stderr}"

    collected = re.search(r"(\d+)\s+tests?\s+collected", proc.stdout)
    assert collected, f"could not read the collected count from:\n{proc.stdout[-500:]}"

    total = int(collected.group(1))
    assert int(badge.group(1)) == total, (
        f"the README claims {badge.group(1)} tests but the suite collects {total}"
    )
