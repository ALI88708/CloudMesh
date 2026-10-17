"""The release notes come from the changelog, and the extraction is tested.

`release.yml` used to cut the section with an inline `awk` that compared the
tag against the heading verbatim: the tag is `v3.5.0` and the heading is
`## [3.5.0] ...`, so nothing ever matched. The failure was invisible by
design -- an empty section fell back to "See CHANGELOG.md for v3.5.0." and the
release went out anyway. The extraction now lives in
`scripts/release_notes.py`, refuses to fall back, and is verified here.
"""

import re
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import release_notes  # noqa: E402

SAMPLE = """\
# Changelog

## [3.5.0] - 2026-10-16

### Fixed

- the thing that broke.

## [3.4.0] - 2026-10-05

### Fixed

- the older thing.
"""


def _write(tmp_path, text: str) -> str:
    """Write a UTF-8 changelog fixture and return its path for CLI arguments."""
    path = tmp_path / "CHANGELOG.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_the_heading_and_its_date_stay_out_of_the_body():
    """Extract only the release body, excluding its version heading and date."""
    body = release_notes.extract_section(SAMPLE, "3.5.0")
    assert body == "### Fixed\n\n- the thing that broke."


@pytest.mark.parametrize("tag", ["3.5.0", "v3.5.0", "V3.5.0"])
def test_the_tag_may_carry_a_leading_v(tmp_path, capsys, tag):
    """Accept bare versions and either case of the optional leading v."""
    changelog = _write(tmp_path, SAMPLE)
    assert release_notes.main([tag, "--changelog", changelog]) == 0
    captured = capsys.readouterr()
    assert captured.out == "### Fixed\n\n- the thing that broke.\n"
    assert captured.err == ""


def test_a_missing_section_fails_instead_of_falling_back(tmp_path, capsys):
    """Report a missing version on stderr without publishing fallback notes."""
    changelog = _write(tmp_path, SAMPLE)
    assert release_notes.main(["v9.9.9", "--changelog", changelog]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "no usable '## [9.9.9]'" in captured.err


@pytest.mark.parametrize("body", ["", "\n", "\n\n"])
@pytest.mark.parametrize("following", ["", "## [3.4.0]\n\n- old\n"])
def test_an_empty_section_fails_too(tmp_path, capsys, body, following):
    """Reject empty release bodies at EOF or before the next release heading."""
    changelog = _write(
        tmp_path, f"## [3.5.0] - 2026-10-16\n{body}{following}"
    )
    assert release_notes.main(["v3.5.0", "--changelog", changelog]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "no usable '## [3.5.0]'" in captured.err
    assert changelog in captured.err


@pytest.mark.parametrize(
    "heading",
    [
        "## [3.5.01] - x",
        "## [13.5.0] - x",
        "## [3x5x0] - x",
        "## [3.5.0-rc.1] - x",
        "## [3.5.0+build.1] - x",
        "### [3.5.0] - x",
        "- See ## [3.5.0] - x",
    ],
)
def test_a_version_does_not_match_a_neighbouring_heading(heading):
    """Reject similar versions and headings outside the release heading format."""
    assert release_notes.extract_section(f"{heading}\n\n- body\n", "3.5.0") is None


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v3.5.0", "3.5.0"),
        ("V3.5.0", "3.5.0"),
        ("3.5.0", "3.5.0"),
        ("v3.5.0-rc.1+build.7", "3.5.0-rc.1+build.7"),
        ("vv3.5.0", "v3.5.0"),
        ("release-v3.5.0", "release-v3.5.0"),
        ("", ""),
    ],
)
def test_version_normalization_removes_only_one_leading_v(tag, expected):
    """Strip a single v or V prefix while preserving the remaining tag text."""
    assert release_notes.version_from_tag(tag) == expected


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("Unreleased", "- pending"),
        ("3.5.0", "### Fixed\n\n- the thing that broke."),
        ("3.4.0", "### Fixed\n\n- the older thing."),
    ],
)
def test_sections_are_selected_at_the_start_middle_and_end(version, expected):
    """Select the requested release regardless of its position in the changelog."""
    changelog = SAMPLE.replace(
        "# Changelog\n", "# Changelog\n\n## [Unreleased]\n\n- pending\n"
    )
    assert release_notes.extract_section(changelog, version) == expected


@pytest.mark.parametrize(
    ("changelog", "expected"),
    [
        ("", None),
        ("# Changelog\n\n- no releases yet\n", None),
        ("## [3.5.0]", ""),
        ("## [3.5.0] - 2026-10-16\n\n", ""),
        ("## [3.5.0]\n- final note", "- final note"),
        ("## [3.5.0]\n- current\n## [3.4.0]\n- old", "- current"),
        ("##\t[3.5.0]\n- current\n##\t[Unreleased]\n- next", "- current"),
    ],
    ids=[
        "empty-changelog", "no-heading", "heading-at-eof", "blank-body-at-eof",
        "body-without-final-newline", "adjacent-sections", "tabbed-headings",
    ],
)
def test_section_boundaries_and_absent_bodies(changelog, expected):
    """Distinguish missing and empty sections while respecting release boundaries."""
    assert release_notes.extract_section(changelog, "3.5.0") == expected


def test_the_body_preserves_markdown_indentation_and_unicode():
    """Preserve Markdown formatting and Unicode within the extracted body."""
    body = (
        "### Fixed\n\n"
        "- Keep trailing spaces for a Markdown line break.  \n"
        "  - nested item: café — 修复\n\n"
        "```python\n    print('ready')\n```\n\n"
        "See [3.4.0] for context; ## [3.4.0] here is inline text."
    )
    changelog = f"## [3.5.0] - today\n\n{body}\n\n## [3.4.0]\n- old\n"

    assert release_notes.extract_section(changelog, "3.5.0") == body


def test_prerelease_and_build_identifiers_are_matched_literally():
    """Match prerelease and build punctuation literally in version headings."""
    version = "3.5.0-rc.1+build.7"
    changelog = (
        "## [3.5.0-rc.1build.7]\n- a different version\n\n"
        f"## [{version}] - today\n\n- release candidate\n\n"
        "## [3.5.0]\n- stable\n"
    )
    assert release_notes.extract_section(changelog, version) == "- release candidate"


def test_main_reads_process_arguments_and_a_utf8_changelog(tmp_path, monkeypatch, capsys):
    """Read process arguments by default and print UTF-8 release notes intact."""
    changelog = _write(tmp_path, "## [3.5.0-rc.1+build.7]\n\n- café — 修复\n")
    monkeypatch.setattr(
        sys, "argv",
        ["release_notes.py", "V3.5.0-rc.1+build.7", "--changelog", changelog],
    )

    assert release_notes.main() == 0
    captured = capsys.readouterr()
    assert captured.out == "- café — 修复\n"
    assert captured.err == ""


@pytest.mark.parametrize(
    ("changelog_text", "status", "stdout"),
    [
        ("## [3.5.0]\n\n- ready\n", 0, "- ready\n"),
        ("## [3.4.0]\n\n- old\n", 1, ""),
        ("## [3.5.0]\n", 1, ""),
    ],
    ids=["success", "missing-section", "empty-section"],
)
def test_script_exits_with_the_extraction_status(
    tmp_path, monkeypatch, capsys, changelog_text, status, stdout,
):
    """Propagate extraction success or failure through the script exit status."""
    changelog = _write(tmp_path, changelog_text)
    script = ROOT / "scripts" / "release_notes.py"
    monkeypatch.setattr(
        sys, "argv", [str(script), "v3.5.0", "--changelog", changelog],
    )

    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(script), run_name="__main__")

    assert exc.value.code == status
    captured = capsys.readouterr()
    assert captured.out == stdout
    if status:
        assert "no usable '## [3.5.0]'" in captured.err
    else:
        assert captured.err == ""


def test_the_current_release_extracts_from_the_real_changelog(
    tmp_path, monkeypatch, capsys,
):
    """Resolve the repository changelog independently of the working directory."""
    declared = re.search(
        r'^version\s*=\s*"([^"]+)"',
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.M,
    )
    assert declared, "pyproject.toml has no version field"
    version = declared.group(1)

    _write(tmp_path, "# An unrelated working directory's changelog\n")
    monkeypatch.chdir(tmp_path)

    assert release_notes.main([f"v{version}"]) == 0
    body = capsys.readouterr().out
    assert body.strip(), "the release body came out empty"
    assert not re.search(r"^##\s+\[", body, re.M), (
        "the extraction crossed into another section"
    )
    assert not re.search(rf"^##\s+\[{re.escape(version)}\]", body, re.M), (
        "the heading line leaked into the body"
    )


def test_the_release_workflow_uses_the_tested_extractor():
    """Keep the release workflow on the tested extractor without silent fallbacks."""
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/release_notes.py" in workflow
    assert "See CHANGELOG.md for" not in workflow, (
        "the silent fallback is back; a release would publish a pointer "
        "instead of its notes"
    )
    assert "awk" not in workflow


def test_the_release_workflow_classifies_the_selected_tag_as_prerelease():
    """Use the selected tag for prerelease classification and release outputs."""
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    prerelease = re.search(r"^\s+prerelease:\s*(.+)$", workflow, re.M)
    assert prerelease, "the release action has no prerelease setting"
    assert prerelease.group(1) == "${{ contains(steps.notes.outputs.tag, '-') }}", (
        "a dispatch from a branch must classify the selected release tag"
    )
    assert "tag_name: ${{ steps.notes.outputs.tag }}" in workflow
    assert "body: ${{ steps.notes.outputs.notes }}" in workflow
