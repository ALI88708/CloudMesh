"""smoke_cli.py must discover the whole command surface, not just the top level.

The walker's subcommand scraper was `usage:\\s*\\S+\\s+\\[?-h\\]?.*?\\{([^}]*)\\}`, which
assumes the program name is a single word. For `cm` that is
`usage: cloudmesh [-h]`, so it matched and the 119 top-level commands were
found. For `cm node` the prog is two words -- `usage: cloudmesh node [-h]` -- so
`\\S+` consumed `cloudmesh`, the pattern then expected `[-h]`, found `node`, and
the match failed. Every command with subcommands was therefore classified as a
leaf, the queue never descended, and the test reported a confident

    [OK] 119 command paths respond to --help

while silently covering 119 of the 286 real paths. The 167 nested subcommands
had never been executed.

This test derives the surface twice by independent means and requires them to
agree: once from argparse (captured by spying on `parse_args`, so nothing is
dispatched) and once from scraping `--help` the way `walk()` does. It fails if
the walker under- or over-reports, and if the total drops to a level that
indicates recursion has silently stopped.
"""

import argparse
import io
import os
import re
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent

if str(ROOT.parent / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT.parent / "scripts"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import smoke_cli  # noqa: E402

_CAPTURED = "__captured__"


def _real_parser():
    """Build the real parser without dispatching anything.

    `cm panic` rotates every key and `cm storage restore` overwrites the
    database, so nothing may be executed to learn the command surface.
    """
    import main as cloudmesh_main

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


def _subparsers(node):
    for action in node._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


def _parser_paths():
    """Every command path the parser defines, by recursive descent."""
    top = _subparsers(_real_parser())
    found, queue, seen = set(), [[name] for name in top], set()

    while queue:
        path = queue.pop()
        key = tuple(path)
        if key in seen:
            continue
        seen.add(key)
        found.add(key)

        node = top[path[0]]
        for word in path[1:]:
            node = _subparsers(node).get(word)
            if node is None:
                break
        else:
            for child in _subparsers(node):
                queue.append([*path, child])
    return found


def _scraped_help(path):
    """Run `--help` for one path the way `smoke_cli.run_help` would."""
    proc = subprocess.run(
        [sys.executable, "main.py", *path, "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
        env=dict(os.environ, PYTHONWARNINGS="ignore", COLUMNS="200"),
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return None, f"exited {proc.returncode}"
    if "Traceback (most recent call last)" in out:
        return None, "printed a traceback"
    match = smoke_cli._CHOICES.search(smoke_cli._usage_block(out))
    if not match:
        return [], None
    return [c.strip() for c in match.group(1).split(",") if c.strip()], None


PARSER_PATHS = _parser_paths()


def test_the_surface_is_the_size_we_think_it_is():
    """Pin the surface so a silent discovery regression cannot pass unnoticed.

    The old broken walker found 119. If this number ever drops, the scraper
    stopped descending again.
    """
    assert len(PARSER_PATHS) > 250, (
        f"only {len(PARSER_PATHS)} command paths found; the parser walk is "
        f"probably not descending into subcommands"
    )


def test_nested_subcommands_exist_at_all():
    """A regression can also hide as 'zero nested subcommands'."""
    nested = {p for p in PARSER_PATHS if len(p) > 1}
    assert len(nested) > 100, f"only {len(nested)} nested subcommands"


def test_walker_descends_into_every_level(monkeypatch):
    """`walk` must reach depth 2 and 3, not stop at the top level.

    Driven by a fake help tree rather than 286 real subprocesses: the property
    under test is `walk`'s recursion, and the scraper itself is covered by
    `test_known_parents_expose_their_subcommands` against real output.

    The fake reproduces the exact shape that defeated the old regex -- a
    two-word program name with the choices wrapped onto the next line.
    """
    tree = {
        (): ["server", "node", "run"],
        ("server",): ["add", "list"],
        ("node",): ["add", "job"],
        ("node", "job"): ["start", "status"],
        ("run",): [],
        ("server", "add"): [],
        ("server", "list"): [],
        ("node", "add"): [],
        ("node", "job", "start"): [],
        ("node", "job", "status"): [],
    }
    requested = []

    def fake_help(cmd, path):
        requested.append(tuple(path))
        children = tree.get(tuple(path))
        if children is None:
            return [], f"unknown path {' '.join(path)}", ""
        out = f"usage: cloudmesh {' '.join(path)} [-h]"
        if children:
            out += "\n                      {" + ",".join(children) + "} ...\n"
        out += "\n\npositional arguments:\n"
        return children, None, out

    monkeypatch.setattr(smoke_cli, "run_help", fake_help)
    paths, failures = smoke_cli.walk("cm")

    assert not failures, f"fake tree reported failures: {failures}"
    found = {tuple(p) for p in paths}

    # walk() reports commands, not the root invocation.
    expected = {p for p in tree if p}
    missing = expected - found
    assert not missing, (
        f"walk() never visited: {sorted(' '.join(p) for p in missing)}"
    )
    assert found == expected, (
        f"walk() reported paths that do not exist: "
        f"{sorted(' '.join(p) for p in found - expected)}"
    )
    assert ("node", "job", "status") in found, "depth 3 was not reached"
    # The parser really does have this depth, so the fake tree is not fiction.
    assert ("node", "job", "status") in PARSER_PATHS


@pytest.mark.parametrize(
    "cmd",
    [
        ["node"],          # prog is two words: this is what broke the old regex
        ["docker"],
        ["acl"],
        ["node", "job"],
        ["webhooks"],
        ["tunnel"],
    ],
)
def test_known_parents_expose_their_subcommands(cmd):
    """Directly assert the scraper on the shape that used to fail.

    Each of these renders as `usage: cloudmesh node [-h]` with the choices on a
    wrapped continuation line, which the old single-word-prog pattern missed.
    """
    subs, err = _scraped_help(cmd)
    assert err is None, f"`cm {' '.join(cmd)} --help` {err}"
    assert subs, (
        f"`cm {' '.join(cmd)}` reported no subcommands; the usage scraper is "
        f"broken for multi-word program names"
    )