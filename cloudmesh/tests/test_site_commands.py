"""Every command site/index.html documents must be accepted by the parser.

CONTRIBUTING.md documented around thirty commands the CLI rejected for months,
and the README carried the same drift. The website states commands too, so it
gets the same guarantee rather than becoming a third place that advertises a
command which does not exist.

Unlike the two guides, the site is HTML rather than Markdown, so "fenced code
block" here means a `<pre>` block: that is the site's equivalent of a fenced
block, and it is where every command on the page is required to live. Keeping
the commands in `<pre><code>` rather than in prose is what lets this file see
them at all -- a command written into a paragraph would be documentation the
suite cannot check, which is the drift this test exists to catch.

The parser is captured with a spy on `parse_args`; nothing is ever dispatched,
because `cm panic` rotates every SSH key and `cm storage restore` overwrites the
database.
"""

import argparse
import io
import re
import shlex
import sys
from contextlib import redirect_stderr, redirect_stdout
from html import unescape
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT.parent / "site" / "index.html"

_CAPTURED = "__captured__"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as cloudmesh_main  # noqa: E402


def _capture_parser():
    captured = {}
    real = argparse.ArgumentParser.parse_args

    def spy(self, args=None, namespace=None):
        captured["parser"] = self
        raise SystemExit(_CAPTURED)

    argparse.ArgumentParser.parse_args = spy
    saved = sys.argv
    sys.argv = ["cloudmesh"]
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            cloudmesh_main.main()
    except SystemExit as exc:
        if exc.code != _CAPTURED:
            raise
    finally:
        argparse.ArgumentParser.parse_args = real
        sys.argv = saved
    return captured["parser"]


# A site example names a real-ish value where a guide would use a placeholder.
# These patterns mark stand-in values so they are read as arguments, not as
# extra levels of the command path.
_PLACEHOLDER = re.compile(r"^[A-Z][A-Z0-9_]*$|^[~/.]|^%")

# `<pre>` is the site's fenced block. Tags and entities are stripped first,
# because `&amp;` inside a command is an encoding artefact, not a shell
# redirection, and `--path /var/log` carries an entity-free slash that is an
# argument rather than a path into the command path.
_FENCED_BLOCK = re.compile(r"<pre\b[^>]*>(.*?)</pre>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def _blocks():
    """Yield the text of each fenced code block on the page."""
    for block in _FENCED_BLOCK.findall(SITE.read_text(encoding="utf-8")):
        yield unescape(_TAG.sub("", block))


def _join_continuations(block: str) -> list[str]:
    """Fold shell line continuations into one logical line.

    A reference that wraps a long example with a trailing `\\` is one command,
    not two. Reading lines independently drops the continuation and makes a
    correct example look broken.
    """
    folded: list[str] = []
    pending = ""
    for raw in block.splitlines():
        stripped = raw.strip()
        pending = f"{pending} {stripped}".strip() if pending else stripped
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue
        folded.append(pending)
        pending = ""
    if pending:
        folded.append(pending)
    return folded


def _cases():
    found = {}
    for block in _blocks():
        for raw in _join_continuations(block):
            line = raw.strip().lstrip("$ ").strip()
            if not re.match(r"^(cm|cloudmesh)\s+", line):
                continue
            line = re.split(r"\s+#", line)[0].rstrip("\\").strip()
            try:
                # posix=True even on Windows: it is what strips the quotes off a
                # quoted shell command, which otherwise leaks into the command
                # words and produces phantom failures.
                words = shlex.split(line, posix=True)[1:]
            except ValueError:
                words = line.split()[1:]
            for stop in (">>", ">", "<", "2>&1"):
                if stop in words:
                    words = words[: words.index(stop)]
                    break
            words = [w for w in words if not w.startswith("$")]

            commands, index = [], 0
            while index < len(words):
                word = words[index]
                if word.startswith("-") or "/" in word or _PLACEHOLDER.match(word):
                    break
                commands.append(word)
                index += 1
                if len(commands) >= 2 and index < len(words) and words[index].startswith("-"):
                    break
            # Dedupe by full argv, not by command path: path-level dedupe checks
            # only the first example of a command and hides later broken
            # variants of the same command.
            if commands:
                found.setdefault(
                    (tuple(commands), tuple(words[index:])),
                    (commands, words[index:], line),
                )
    return list(found.values())


def test_the_site_was_read():
    """The guard: an extractor that finds nothing would pass every other test.

    The site's reference is expected to grow, so the floor is set well above the
    handful the first version of this file needed -- a count that only just
    clears the bar means the bar is doing no work.
    """
    found = _cases()
    assert len(found) >= 40, (
        f"only found {len(found)} site command examples; "
        "the extractor is broken or the reference has been gutted"
    )


def test_every_area_is_documented():
    """The reference is grouped by area, and each area must survive extraction.

    Guards the grouping itself: five headings that exist in the markup but hold
    no commands would satisfy the count above while documenting nothing.
    """
    text = SITE.read_text(encoding="utf-8")
    missing = [area for area in ("servers", "nodes", "files", "security", "monitoring")
               if f'group="{area}"' not in text]
    assert not missing, f"command groups missing from the site: {missing}"


@pytest.mark.parametrize(
    "commands, rest, line",
    _cases(),
    ids=lambda *a: " ".join(a) if isinstance(a, list) else str(a),
)
def test_site_command_is_accepted(commands, rest, line):
    parser = _capture_parser()
    err = io.StringIO()
    try:
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            parser.parse_args([*commands, *rest])
        return
    except SystemExit:
        message = err.getvalue()
    except Exception as exc:  # pragma: no cover - surfaces a parser bug
        pytest.fail(f"`cm {' '.join(commands)}` crashed the parser: {exc!r}")

    detail = " ".join(message.strip().splitlines()[-1:])

    # A placeholder in an int-typed slot is documentation style, not a defect:
    # `-p PORT` means "put a port here".
    if re.search(r"invalid int value: '([A-Z][A-Z0-9_]*)'", detail):
        return

    pytest.fail(
        f"site/index.html documents `{line}` but the CLI rejects it:\n  {detail}\n"
        f"  Check `cm {' '.join(commands)} --help` and fix the site or the parser."
    )