"""Every command CONTRIBUTING.md documents must be accepted by the parser.

CONTRIBUTING.md carried commands that never existed — `cm node start`,
`cm node stop`, `cm node status` (those are node-agent subcommands, not
controller ones), `cm alias add/list/remove` (alias takes flags), and
`cm backup list/create/restore` (backup takes --restore). Half the document was
aspirational.

This parses the guide's code blocks and runs each invocation through the real
argparse parser, so a future doc drift fails the suite.

The parser is captured with a spy on `parse_args`; nothing is ever dispatched,
because `cm panic` rotates every key and `cm storage restore` overwrites the
database.
"""

import argparse
import io
import os
import re
import shlex
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
DOC = REPO / "CONTRIBUTING.md"

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


# Docs use these as stand-in values; they are not literal arguments.
_PLACEHOLDER = re.compile(r"^[A-Z][A-Z0-9_]*$|^[~/.]|^%|^\$")
# Redirections and shell variables are not command arguments.
_NOT_ARGUMENTS = re.compile(r"^(>>|>|<|2>&1|&\d+)$")


def _join_continuations(block: str) -> list[str]:
    """Fold shell line continuations into one logical line.

    The guide writes `cm plugins add --name sysinfo \\` on one line and
    `--command "..."` on the next. Reading lines independently dropped the
    continuation, so `--command` vanished and five correct examples looked
    broken.
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


def _documented_invocations():
    """Yield (command words, rest of argv) for each documented example."""
    text = DOC.read_text(encoding="utf-8")
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.S):
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
            # A redirect and everything after it is shell, not arguments:
            # `cm completions bash >> ~/.bashrc` documents a redirect, not an arg.
            for stop in (">>", ">", "<", "2>&1", "2>"):
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
            if commands:
                yield commands, words[index:], line


# Commands whose examples legitimately omit a required value, because showing a
# real password or host would be wrong in a public guide. Each is documented here
# rather than silently skipped, so the exemption is reviewable.
OPTIONAL_VALUE_COMMANDS = {
    "acl add-user", "acladd",
    "database query", "dbq", "database backup", "dbbak", "database status", "dbstatus",
    "notify setup-telegram",
    "webhooks add",
    # User-defined aliases: `cm myalias` is the guide's own example of an alias
    # the reader creates, not a command the CLI ships.
    "myalias",
}


def _cases():
    """Dedupe by the full argv, not by command path.

    Dedupe-by-path checks only the first example of each command, which hid a
    real defect: `cm transfer --file X --to-server Y --download` was broken
    (`--download` does not exist) while the earlier `cm transfer` example in the
    same section was already fixed, so the path-level dedupe reported the whole
    command as fine. Every distinct invocation has to be checked.
    """
    seen = {}
    for commands, rest, line in _documented_invocations():
        seen.setdefault((tuple(commands), tuple(rest)), (commands, rest, line))
    return list(seen.values())


CASES = _cases()
SKIPPED = [c for c in CASES if " ".join(c[0]) in OPTIONAL_VALUE_COMMANDS]


def test_the_guide_was_read():
    assert len(CASES) >= 100, f"only found {len(CASES)} documented commands; extractor is broken"


@pytest.mark.parametrize(
    "commands, rest, line",
    [c for c in CASES if " ".join(c[0]) not in OPTIONAL_VALUE_COMMANDS],
    ids=lambda *a: " ".join(a) if isinstance(a, list) else str(a),
)
def test_documented_command_is_accepted(commands, rest, line):
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
    invalid_int = re.search(r"invalid int value: '([A-Z][A-Z0-9_]*)'", detail)
    if invalid_int:
        return

    pytest.fail(
        f"CONTRIBUTING.md documents `{line}` but the CLI rejects it:\n  {detail}\n"
        f"  Check `cm {' '.join(commands)} --help` and fix the guide or the parser."
    )