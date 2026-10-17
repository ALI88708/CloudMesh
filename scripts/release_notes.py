#!/usr/bin/env python3
"""Print one version's section of CHANGELOG.md, for the Release workflow.

The workflow names the release after a tag (`v3.5.0`) while the changelog
heading carries the bare version (`## [3.5.0] - 2026-10-16`), so the tag's
leading `v` is stripped before matching. The inline `awk` this replaces
compared `v3.5.0` against a heading carrying no `v`, matched nothing, and fell
back to "See CHANGELOG.md for v3.5.0." -- which is the body the first tagged
release would have shipped with.

A missing or empty section exits 1. A release whose notes are a pointer is a
release nobody can audit, so this refuses to produce one.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

_ANY_HEADING = re.compile(r"^##\s+\[", re.MULTILINE)


def version_from_tag(tag: str) -> str:
    """Remove one leading `v` or `V`, leaving the rest of the tag unchanged.

    `v3.5.0` and `3.5.0` both name the version `3.5.0`.
    """
    return tag[1:] if tag[:1] in ("v", "V") else tag


def extract_section(changelog: str, version: str) -> str | None:
    """The body under `## [version]`, or None if absent or whitespace-only.

    The body ends at the next `## [...]` heading. The version is matched
    exactly, so asking for `3.5.0` cannot pick up `## [3.5.01]`.
    Only leading and trailing newline characters are stripped from nonempty
    notes; other whitespace is preserved.
    """
    heading = re.compile(rf"^##\s+\[{re.escape(version)}\][^\n]*\n?", re.MULTILINE)
    match = heading.search(changelog)
    if match is None:
        return None
    rest = changelog[match.end() :]
    following = _ANY_HEADING.search(rest)
    if following is not None:
        rest = rest[: following.start()]
    return rest.strip("\n") if rest.strip() else None


def main(argv: list[str] | None = None) -> int:
    """Print the tag's changelog section to stdout and return 0 on success.

    Parse argv, or sys.argv[1:] when None, accepting a tag and an optional
    --changelog path (default: the repository's CHANGELOG.md). A missing or
    whitespace-only section prints an error to stderr and returns 1.

    Argument parsing raises SystemExit for help or invalid arguments. File
    access errors (OSError) and UTF-8 decoding errors (UnicodeDecodeError)
    propagate to the caller.
    """
    parser = argparse.ArgumentParser(
        description="Print one version's CHANGELOG.md section for a release.",
    )
    parser.add_argument("tag", help="the release tag, e.g. v3.5.0")
    parser.add_argument(
        "--changelog",
        default=str(DEFAULT_CHANGELOG),
        help="path to CHANGELOG.md (default: the repository's own)",
    )
    args = parser.parse_args(argv)

    version = version_from_tag(args.tag)
    changelog = Path(args.changelog).read_text(encoding="utf-8")
    section = extract_section(changelog, version)

    if not section:
        print(
            f"release_notes: no usable '## [{version}]' section in "
            f"{args.changelog}. A release is never allowed to fall back to a "
            "pointer; write the changelog entry before publishing.",
            file=sys.stderr,
        )
        return 1

    print(section)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
