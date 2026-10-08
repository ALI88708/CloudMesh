"""Run the README's documented commands through the real parser.

CONTRIBUTING.md was the worst offender, but the README carries the same class of
drift: it advertises `cm transfer -s SERVER -l PATH -r PATH`, and none of those
three options exist on `transfer`.

Reuses the extractor and the capture helper from the CONTRIBUTING test so the
two cannot disagree about how a documented invocation is read.
"""
import argparse
import io
import re
import shlex
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
README = REPO / "README.md"

_CAPTURED = "__captured__"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as cloudmesh_main  # noqa: E402

_PLACEHOLDER = re.compile(r"^[A-Z][A-Z0-9_]*$|^[~/.]|^%")
_REDIRECT = re.compile(r"^(>>|>|<|2>&1|2>)$")


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


def _join_continuations(block: str) -> list[str]:
    """Fold shell line continuations into one logical line.

    `cm plugins add --name sysinfo \\` followed by `--command "..."` is one
    command. Reading lines independently dropped the continuation and made
    correct examples look broken.
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
    text = README.read_text(encoding="utf-8")
    found = {}
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.S):
        for raw in _join_continuations(block):
            line = raw.strip().lstrip("$ ").strip()
            if not re.match(r"^(cm|cloudmesh)\s+", line):
                continue
            line = re.split(r"\s+#", line)[0].rstrip("\\").strip()
            try:
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
            # only the first example and hides later broken variants of the same
            # command.
            if commands:
                found.setdefault(
                    (tuple(commands), tuple(words[index:])),
                    (commands, words[index:], line),
                )
    return list(found.values())


# README examples that intentionally omit a value, or that name a
# user-defined thing rather than a shipped command. Keys are command paths with
# no "cm " prefix, because that is what the join produces.
EXEMPT = {"update", "test"}


def test_readme_was_read():
    assert len(_cases()) >= 40, "extractor found too few README examples"


@pytest.mark.parametrize(
    "commands, rest, line",
    [c for c in _cases() if " ".join(c[0]) not in EXEMPT],
    ids=lambda *a: " ".join(a) if isinstance(a, list) else str(a),
)
def test_readme_command_is_accepted(commands, rest, line):
    parser = _capture_parser()
    err = io.StringIO()
    try:
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            parser.parse_args([*commands, *rest])
        return
    except SystemExit:
        message = err.getvalue()
    except Exception as exc:  # pragma: no cover
        pytest.fail(f"`cm {' '.join(commands)}` crashed the parser: {exc!r}")

    detail = " ".join(message.strip().splitlines()[-1:])
    if re.search(r"invalid int value: '([A-Z][A-Z0-9_]*)'", detail):
        return
    pytest.fail(
        f"README.md documents `{line}` but the CLI rejects it:\n  {detail}"
    )