"""No argument vector may crash the CLI with an uncaught traceback.

This is the highest-value property in the verification work. It reaches every
command's parser without enumerating commands by hand, and an uncaught
traceback is the defect class that reached a release three times in the last
month.

Parsing is exercised in-process by spying on `parse_args`, so nothing is
dispatched and no command can act. That matters here: `cm panic` rotates every
SSH key and `cm storage restore` overwrites the database, so the suite must
never actually run a command to learn what it does.
"""

import argparse
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as cloudmesh_main  # noqa: E402

_CAPTURED = "__captured__"


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


def _command_names(parser):
    """Every top-level command name the CLI registers."""
    return sorted(parser._subparsers._group_actions[0].choices)


# Built once: the parser is large and `main()` re-derives it from scratch on
# every call, so rebuilding it per example would dominate the runtime.
PARSER = _capture_parser()
COMMANDS = _command_names(PARSER)

# Tokens that are not commands. `--nope` and `-x` are unknown options, `..` and
# `CON` are path-shaped payloads, and `""` is the empty positional that a
# shell loop or a bug in argument assembly can produce. They matter because the
# fuzzing that finds defects is in what the parser does with *wrong* input.
NOT_COMMANDS = ["--nope", "-x", "..", "CON", ""]

# Built from NOT_COMMANDS rather than COMMANDS alone so the strategy stays
# constructible even if command discovery breaks; the non-vacuous guarantee is
# `test_command_names_were_discovered`, which fails with a readable message.
ARGV_TOKENS = COMMANDS + NOT_COMMANDS


def test_command_names_were_discovered():
    """A fuzz run over an empty token set proves nothing, so guard against it."""
    assert len(COMMANDS) >= 40, (
        f"only {len(COMMANDS)} command names discovered from the parser; the "
        f"extraction is broken, so the fuzz property would be vacuous: {COMMANDS}"
    )


# pytest.ini caps every test at 10s. A cold Hypothesis run peaks around 4s on a
# fast machine, which leaves too little margin for a slower or loaded CI
# runner, so the cap is raised here. This is the harness's hang detector, not
# the property: raising it cannot make a failing assertion pass.
@pytest.mark.timeout(120)
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.sampled_from(ARGV_TOKENS)))
def test_no_argument_vector_produces_a_traceback(argv):
    """`SystemExit` is a normal outcome; anything else is a defect.

    argparse refusing to parse a nonsense command is correct behaviour, so a
    `SystemExit` here is a pass. The failure mode this exists to catch is a
    `type=` callable, a `choices` comparison, or a subparser branch raising
    something the CLI's `main()` never anticipated -- which reaches the user
    as a raw traceback.
    """
    err = io.StringIO()
    try:
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            PARSER.parse_args(argv)
    except SystemExit:
        pass  # argparse rejecting input is a normal outcome
    except Exception as exc:  # noqa: BLE001 - the point is to catch anything
        raise AssertionError(
            f"argv {argv!r} raised {type(exc).__name__}: {exc}\n"
            f"  Reproduce with: PARSER.parse_args({argv!r})"
        ) from exc

    # Nothing should have printed a traceback to stderr either: a handler that
    # catches the error and then dumps a traceback is the same defect wearing a
    # different hat.
    captured = err.getvalue()
    assert "Traceback (most recent call last)" not in captured, (
        f"argv {argv!r} printed a traceback to stderr:\n{captured}"
    )


# Reserved Windows device names and the shapes a bad join produces. Listed
# explicitly rather than left to `st.text` so coverage of them is guaranteed
# instead of merely likely: `st.text` would reach "CON" within 200 examples,
# but "NUL" is not something a fuzzer reliably stumbles onto.
EDGE_NAMES = st.sampled_from(
    ["CON", "NUL", "PRN", "AUX", "COM1", "LPT1", "..", ".", " ", "\\", "\\\\", "C:\\", "C:\\Windows"]
)

# Excludes `/` and NUL: those are path separators and terminators, and on
# Windows a NUL anywhere in a path raises at the syscall layer rather than in
# the resolver. Surrogates are excluded because they cannot round-trip through
# the filesystem at all, which would test the encoding layer, not the resolver.
# Everything else is fair game -- spaces, backslashes, dot runs, reserved
# device names -- because CloudMesh ships on Linux and Windows and has to
# survive all of it.
PATH_TEXT = st.text(
    alphabet=st.characters(blacklist_characters="/\x00", blacklist_categories=("Cs",)),
    max_size=40,
)

PATH_STRATEGY = st.one_of(PATH_TEXT, EDGE_NAMES)


@pytest.mark.timeout(120)
@settings(max_examples=200, deadline=None)
@given(PATH_STRATEGY)
def test_paths_never_crash_resolution(name):
    """`resolve_base_dir` may refuse a path; it may not explode on one.

    `OSError` is the legitimate refusal -- an unwritable or nonexistent path is
    an answer, not a bug. Any other exception type means the resolver is doing
    something with the string that was never anticipated.
    """
    from core.storage import resolve_base_dir

    try:
        resolve_base_dir(name)
    except OSError:
        pass  # an unwritable path is a legitimate refusal
    except Exception as exc:  # noqa: BLE001 - the point is to catch anything
        raise AssertionError(
            f"resolve_base_dir({name!r}) raised {type(exc).__name__}: {exc}"
        ) from exc
