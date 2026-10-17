"""The release notes come from the changelog, and the extraction is tested.

`release.yml` used to cut the section with an inline `awk` that compared the
tag against the heading verbatim: the tag is `v3.5.0` and the heading is
`## [3.5.0] ...`, so nothing ever matched. The failure was invisible by
design -- an empty section fell back to "See CHANGELOG.md for v3.5.0." and the
release went out anyway. The extraction now lives in
`scripts/release_notes.py`, refuses to fall back, and is verified here.
"""

import re
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
    path = tmp_path / "CHANGELOG.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_the_heading_and_its_date_stay_out_of_the_body():
    body = release_notes.extract_section(SAMPLE, "3.5.0")
    assert body == "### Fixed\n\n- the thing that broke."


def test_the_tag_may_carry_a_leading_v(tmp_path, capsys):
    changelog = _write(tmp_path, SAMPLE)
    with_v = release_notes.main(["v3.5.0", "--changelog", changelog])
    output = capsys.readouterr().out
    bare = release_notes.main(["3.5.0", "--changelog", changelog])
    assert with_v == bare == 0
    assert capsys.readouterr().out == output
    assert output.strip()


def test_a_missing_section_fails_instead_of_falling_back(tmp_path, capsys):
    changelog = _write(tmp_path, SAMPLE)
    assert release_notes.main(["v9.9.9", "--changelog", changelog]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "no usable '## [9.9.9]'" in captured.err


def test_an_empty_section_fails_too(tmp_path, capsys):
    changelog = _write(
        tmp_path, "## [3.5.0] - 2026-10-16\n\n## [3.4.0] - 2026-10-05\n\n- old\n"
    )
    assert release_notes.main(["v3.5.0", "--changelog", changelog]) == 1
    assert "no usable '## [3.5.0]'" in capsys.readouterr().err


@pytest.mark.parametrize("heading", ["## [3.5.01] - x", "## [13.5.0] - x"])
def test_a_version_does_not_match_a_neighbouring_heading(heading):
    assert release_notes.extract_section(f"{heading}\n\n- body\n", "3.5.0") is None


def test_the_current_release_extracts_from_the_real_changelog(capsys):
    declared = re.search(
        r'^version\s*=\s*"([^"]+)"',
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.M,
    )
    assert declared, "pyproject.toml has no version field"
    version = declared.group(1)

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
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/release_notes.py" in workflow
    assert "See CHANGELOG.md for" not in workflow, (
        "the silent fallback is back; a release would publish a pointer "
        "instead of its notes"
    )
    assert "awk" not in workflow
