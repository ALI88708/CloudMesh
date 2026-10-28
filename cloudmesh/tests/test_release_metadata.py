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

The CHANGELOG is held to the same standard, and it had drifted the same way:
two `## [Unreleased]` sections, one of them below a released version, and a
`[3.5.2]` with no `[3.5.0]` or `[3.5.1]` beneath it even though no 3.5.x was
ever cut. Only structure is checked, not prose -- prose is not mechanically
checkable, and structure is what went wrong.

RELEASE is the one place a human states the version being prepared. Everything
else is compared against it or against `pyproject.toml`, so cutting a release
is one edit here plus the file it describes.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent

RELEASE = "4.2.5"

_H2 = re.compile(r"^##\s+\[([^\]]+)\]", re.M)
_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)\b")


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _declared_version() -> str:
    """The version in pyproject.toml, which is the single source of truth."""
    declared = re.search(r'^version\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.M)
    assert declared, "pyproject.toml has no version field"
    return declared.group(1)


def test_the_python_floor_is_3_11():
    pyproject = _read("pyproject.toml")
    assert re.search(r'^requires-python\s*=\s*">=3\.11"', pyproject, re.M)
    assert "Programming Language :: Python :: 3.10" not in pyproject
    assert "Programming Language :: Python :: 3.11" in pyproject


def test_the_readme_python_badge_is_3_11():
    readme = _read("README.md")
    assert "Python-3.11" in readme
    assert "Python-3.10" not in readme


def test_the_site_python_floor_is_3_11():
    site = _read("site/index.html")
    assert "Python</strong> 3.11+" in site
    assert "PYTHON 3.11+" in site
    assert "3.10+" not in site


def test_ci_matrix_drops_python_3_10():
    workflow = _read(".github/workflows/ci.yml")
    assert '"3.10"' not in workflow
    assert '"3.11"' in workflow


def test_the_bsd_gate_runs_on_the_branches_that_carry_released_code():
    """`docs/LTS.md` names the BSD VM as part of the release gate.

    The FreeBSD workflow only triggered on `feature/bsd-support`, so no
    released commit had ever been checked on FreeBSD and the policy was
    satisfied by assertion rather than by a green run. The trigger has to
    cover the branches that ship.
    """
    workflow = _read(".github/workflows/bsd.yml")
    trigger = workflow.split("on:", 1)[1].split("permissions:", 1)[0]
    assert 'branches: [ main, "release/**" ]' in trigger
    assert "feature/bsd-support" not in trigger


def test_the_bsd_e2e_script_does_not_hardcode_a_version():
    """The FreeBSD gate went red on every release after 4.0.0.

    The script asserted that `cm --version` reports 4.0.0 -- a number
    written when the BSD support branch was cut. The check has to follow
    the version in pyproject.toml, or it fails on a version bump and says
    nothing at all about the released code.
    """
    script = _read("scripts/bsd_e2e.sh")
    # The comment above the check explains the history and names the old
    # number, so the comparison is read from the code alone.
    code = "\n".join(
        line for line in script.splitlines() if not line.strip().startswith("#")
    )
    assert "pyproject.toml" in code
    assert "4.0.0" not in code


def test_the_lts_policy_names_the_support_window():
    policy = _read("docs/LTS.md")
    assert "2027-10-20" in policy
    assert "3.11" in policy
    assert "P0" in policy and "P1" in policy


def test_the_upgrade_guide_names_the_breaking_changes():
    guide = _read("docs/UPGRADING.md")
    for token in ("3.4.0", "4.1.2", "--enable-exec", "3.11", "SHA256SUMS"):
        assert token in guide


def test_the_upgrade_guide_carries_the_drill_findings():
    """The drill turned up two traps that are silent when they are hit.

    3.4.0 ignores `CLOUDMESH_DIR` while 4.1.2 honours it, so a user who
    leaves the variable set sees an empty server list after the upgrade. And
    3.4.0's `cm config import` neither carries the SQLite database nor
    creates missing files, so a rollback onto a fresh install loses the
    server list. The guide is the only place either fact is written down.
    """
    guide = _read("docs/UPGRADING.md")
    for token in ("CLOUDMESH_DIR", "cm migrate --verify", "cloudmesh.db"):
        assert token in guide, f"the upgrade guide no longer mentions {token}"
    assert "Upgrade drill record" in guide


def test_the_security_policy_lists_the_lts_line():
    policy = _read("SECURITY.md")
    assert "4.1.x" in policy
    assert "2027-10-20" in policy


def test_the_contributing_guide_states_the_real_security_test_count():
    """The guide says which file a security change has to extend, and how
    big that file is.

    The count was hand-written and drifted: it said 63 tests for a file
    that collected 97, for the same reason the badges drifted -- nothing
    compared the number with the file. This derives it.
    """
    guide = _read("CONTRIBUTING.md")
    claimed = re.search(r"test_security\.py` \(currently \*\*(\d+) tests\*\*\)", guide)
    assert claimed, "the contributing guide no longer states the security test count"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_security.py",
            "--collect-only",
            "-q",
            "--no-header",
        ],
        cwd=str(ROOT / "cloudmesh"),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, f"collection failed:\n{proc.stdout}\n{proc.stderr}"
    collected = re.search(r"(\d+)\s+tests?\s+collected", proc.stdout)
    assert collected, f"could not read the collected count from:\n{proc.stdout[-500:]}"
    assert int(claimed.group(1)) == int(collected.group(1)), (
        f"the guide claims {claimed.group(1)} security tests "
        f"but the file collects {collected.group(1)}"
    )


def test_runtime_version_uses_installed_metadata(monkeypatch):
    import importlib.metadata
    from unittest.mock import Mock

    from cloudmesh.core.features import get_version

    lookup = Mock(return_value="9.8.7+installed")
    monkeypatch.setattr(importlib.metadata, "version", lookup)

    assert get_version() == {
        "version": "9.8.7+installed",
        "python": ".".join(map(str, sys.version_info[:3])),
        "platform": sys.platform,
    }
    lookup.assert_called_once_with("cloudmesh")


@pytest.mark.parametrize("failure", ["missing-distribution", "broken-metadata"])
def test_runtime_version_fallback_matches_declared_release(monkeypatch, failure):
    import importlib.metadata
    from unittest.mock import Mock

    from cloudmesh.core.features import get_version

    error = (
        importlib.metadata.PackageNotFoundError("cloudmesh")
        if failure == "missing-distribution"
        else RuntimeError("metadata is unreadable")
    )
    monkeypatch.setattr(importlib.metadata, "version", Mock(side_effect=error))

    assert get_version()["version"] == _declared_version()


def test_runtime_version_fallback_when_metadata_cannot_be_imported(monkeypatch):
    from cloudmesh.core.features import get_version

    monkeypatch.setitem(sys.modules, "importlib.metadata", None)

    assert get_version()["version"] == _declared_version()


def _sections() -> list[str]:
    """The bracketed heading of every `##` section, in file order."""
    return _H2.findall(_read("CHANGELOG.md"))


def _version_of(token: str) -> tuple[int, int, int] | None:
    """Parse a section heading as a version, or None if it is not one."""
    found = _VERSION.match(token.strip())
    return tuple(int(part) for part in found.groups()) if found else None


def test_pyproject_declares_the_released_version():
    """The single source of truth for the version number."""
    declared = _declared_version()
    assert declared == RELEASE, (
        f"pyproject says {declared}; this release is {RELEASE}. Bumping the "
        "minor resets the patch, so the first release of a 3.5 series is 3.5.0."
    )


def test_the_readme_version_badge_agrees_with_pyproject():
    """A badge is what a user reads first; a stale one misstates the release."""
    declared = _declared_version()
    badge = re.search(r"Version-([0-9.]+)-", _read("README.md"))
    assert badge, "the README has no Version badge"
    assert badge.group(1) == declared, (
        f"the README badge says {badge.group(1)} but pyproject says {declared}"
    )


def _site_versions() -> list[str]:
    """Every version literal the site states in its own markup.

    The release cards are fetched from the GitHub API at runtime, so the static
    page carries no historical versions: anything version-shaped here is a claim
    about the current release. Four-part dotted numbers are IPv4 addresses from
    the command examples, not versions.
    """
    text = _read("site/index.html")
    return [
        match.group(0)
        for match in _VERSION.finditer(text)
        if not re.match(r"\.\d", text[match.end() : match.end() + 2])
    ]


def test_the_site_version_claim_agrees_with_pyproject():
    """The site stated 3.5.1 while every other surface said 3.5.0.

    `test_site_commands.py` re-checks the commands the page shows against the
    parser, but says nothing about the version in the prose introducing them, so
    that number drifted with nothing to catch it.
    """
    stated = _site_versions()
    assert stated, "site/index.html states no version to check"
    declared = _declared_version()
    stale = sorted({version for version in stated if version != declared})
    assert not stale, (
        f"site/index.html advertises {', '.join(stale)} but pyproject "
        f"declares {declared}"
    )


def test_the_changelog_documents_the_current_version():
    """A release without a changelog entry is a release nobody can audit."""
    declared = _declared_version()
    assert re.search(rf"^## \[{re.escape(declared)}\]", _read("CHANGELOG.md"), re.M), (
        f"CHANGELOG.md has no [{declared}] section"
    )


def test_the_changelog_has_at_most_one_unreleased_section():
    """Two of them is how the same notes get written twice and then diverge."""
    unreleased = [t for t in _sections() if t.strip().lower() == "unreleased"]
    assert len(unreleased) <= 1, (
        f"CHANGELOG.md has {len(unreleased)} [Unreleased] sections; work "
        "recorded in one of them is invisible from the other"
    )


def test_no_unreleased_section_sits_below_a_released_one():
    """`[Unreleased]` is the newest entry by definition, so it goes first.

    Vacuously true once a release is cut and the section is gone, which is the
    state this guards for. The section was below `[3.5.2]` while describing
    work dated before it, so the file advertised as pending something older
    than a release it already called shipped.
    """
    tokens = _sections()
    for index, token in enumerate(tokens):
        if token.strip().lower() == "unreleased":
            assert index == 0, (
                f"an [Unreleased] section is at position {index}, below "
                f"[{tokens[0]}], so its contents are older than a version the "
                "file already calls released"
            )


def test_the_changelog_lists_versions_newest_first():
    """A reader scans down for the version they run; order is the index."""
    versions = [v for v in (_version_of(t) for t in _sections()) if v is not None]
    for newer, older in zip(versions, versions[1:]):
        assert newer > older, (
            f"[{'.'.join(map(str, newer))}] is listed above "
            f"[{'.'.join(map(str, older))}], which is newer"
        )


def test_every_minor_series_is_documented_down_to_patch_zero():
    """A patch above .0 implies the .0 under it, or the number came from nowhere.

    The file went from `[3.4.0]` to `[3.5.2]` with nothing between, so it
    described a release that no series had produced. Bumping the minor resets
    the patch, so the bottom of a 3.5 series is 3.5.0 whatever follows it.
    """
    lowest: dict[tuple[int, int], int] = {}
    for version in (v for v in (_version_of(t) for t in _sections()) if v):
        major, minor, patch = version
        key = (major, minor)
        lowest[key] = min(lowest.get(key, patch), patch)

    for (major, minor), patch in lowest.items():
        assert patch == 0, (
            f"the lowest {major}.{minor} section is {major}.{minor}.{patch}; "
            f"there is no [{major}.{minor}.0] section in the file"
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


# `pytest.ini` caps every test at 10s. This one collects the whole suite in a
# subprocess bounded at 300s, a budget the cap made unreachable: the guard timed
# out on a loaded machine while its own bound sat untouched. One test needs the
# longer budget, not the file.
@pytest.mark.timeout(330)
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
