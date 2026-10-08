"""Every alias must accept exactly what the command it aliases accepts.

The aliases were hand-copies of their canonical parser's `add_argument` calls,
and they drifted. `cm mon --local` is advertised in the README and in
CONTRIBUTING.md, and it failed with "unrecognized arguments" because the `mon`
parser never declared `--local`. `cm cp` was worse: it declared `--server`,
`--local`, and `--direction`, none of which `cmd_transfer` reads, so the command
could not have worked at all.

Aliases are now cloned from the canonical parser by `_alias_of`. This test
fails if anyone reintroduces a hand-written alias that disagrees with its
canonical command.
"""

import argparse
import io
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as cloudmesh_main

_CAPTURED = "__captured__"
ALIAS_MARKER = "[alias]"


def _capture_parser():
    """Build the real parser without dispatching anything."""
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


def _tops():
    parser = _capture_parser()
    action = parser._subparsers._group_actions[0]
    return dict(action.choices)


def _options(parser) -> set[str]:
    found: set[str] = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            found.add("<subcommands>")
            continue
        if action.option_strings:
            found.update(o for o in action.option_strings if o not in ("-h", "--help"))
        else:
            found.add(f"<{action.dest}>")
    return found


def _pairs():
    """Yield (alias, canonical, tops) for every cloned alias.

    ALIAS_REGISTRY is the source of truth: _alias_of records the canonical name
    as it builds each alias, so this cannot drift the way a source-text scan did.
    """
    tops = _tops()
    registry = getattr(cloudmesh_main, "ALIAS_REGISTRY", {})
    for alias in sorted(registry):
        canonical = registry[alias]
        if canonical not in tops or alias not in tops:
            continue
        if tops[alias] is tops[canonical]:
            continue
        yield alias, canonical, tops


PAIRS = list(_pairs())


# Top-level aliases that are pure clones of a canonical command. The other
# aliases (`fwadd`, `dcls`, `dbq`, ...) dispatch through an `_alias_*` shim that
# hardcodes a subcommand action and fills defaults, so they are deliberately not
# clones and are covered by the command-surface smoke test instead.
EXPECTED_CLONES = {
    "mon": "monitor",
    "dash": "dashboard",
    "up": "uptime",
    "df": "disk",
    "net": "network",
    "log": "logs",
    "cp": "transfer",
    "dec": "decrypt",
}


def test_aliases_were_discovered():
    """Guards the guard: a discovery failure must not read as 'no drift'."""
    discovered = {alias: canonical for alias, canonical, _ in PAIRS}

    missing = {
        alias: canonical
        for alias, canonical in EXPECTED_CLONES.items()
        if discovered.get(alias) != canonical
    }
    assert not missing, (
        f"cloned aliases missing or remapped: {missing}. "
        f"Discovered: {sorted(discovered)}"
    )


@pytest.mark.parametrize(
    "alias, canonical, tops",
    PAIRS,
    ids=[f"{a}-vs-{c}" for a, c, _ in PAIRS],
)
def test_alias_matches_its_canonical(alias, canonical, tops):
    missing = _options(tops[canonical]) - _options(tops[alias])
    extra = _options(tops[alias]) - _options(tops[canonical])

    assert not missing and not extra, (
        f"`cm {alias}` drifted from `cm {canonical}`"
        f"{f'; missing {sorted(missing)}' if missing else ''}"
        f"{f'; extra {sorted(extra)}' if extra else ''}"
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["mon", "--local"],          # README: "cm mon --local"
        ["dash", "--live"],
        ["dash", "--interval", "5"],
        ["up", "--name", "srv"],
        ["df", "--name", "srv"],
        ["net", "--name", "srv"],
        ["log", "--name", "srv"],
        ["cp", "--to-server", "srv", "--file", "f"],
        ["dec", "f", "-k", "KEY"],    # decrypt requires --key
    ],
    ids=lambda a: " ".join(a),
)
def test_documented_alias_invocation_parses(argv, monkeypatch, capsys):
    """The exact forms the README and CONTRIBUTING show must be accepted."""
    calls = []
    monkeypatch.setattr(
        cloudmesh_main, "_lookup_handler", lambda *_a: calls.append(argv) or (lambda: None)
    )
    monkeypatch.setattr(sys, "argv", ["cloudmesh", *argv])

    try:
        cloudmesh_main.main()
    except SystemExit as exc:
        assert exc.code in (0, 1, 2), f"unexpected exit {exc.code}"
        if exc.code == 2:
            out = capsys.readouterr()
            pytest.fail(f"`cm {' '.join(argv)}` was rejected:\n{out.out}{out.err}")

    out = capsys.readouterr().out
    assert "Traceback" not in out
    assert calls == [argv], f"alias did not dispatch to its handler: {calls}"