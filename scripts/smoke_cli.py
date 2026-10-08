#!/usr/bin/env python3
"""Walk every command the CLI advertises and fail on the first broken one.

CI used to run `--help` on three commands, which is why `cm api`,
`cm panic rotate`, `cm weather`, and four others shipped raising NameError or
UnboundLocalError the first time anybody ran them. This walks the whole command
surface by parsing the usage banner: for every top-level command it asks for
help, and for every subcommand it recurses.

Runs against whichever `cm` is on PATH, so it verifies an installed release
rather than the checkout.

Usage:
    python scripts/smoke_cli.py [--cmd cm] [--jobs 8] [--quiet]
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

# `{a,b,c}` immediately after the program name in a usage banner.
_HELP_FLAGS = ("-h", "--help")

# The subcommand list inside argparse's usage block, e.g.
#   usage: cloudmesh node [-h]
#                         {add,remove,list,...} ...
#
# Two properties distinguish it from an option's allowed values:
#
#   * argparse terminates a subparser list with an ellipsis, so `{a,b} ...`.
#     An option's choices render as `[--level {error,warn,info,debug}]` and
#     never carry one.
#   * the braces come after `[-h]`, where argparse places subparsers. A
#     positional metavar such as `{action}` can also render as braces, but
#     never before the optionals.
#
# Matching any brace group after `[-h]` was enough to find the 119 top-level
# commands, which is why the bug stayed hidden: it also matched
# `[--level {error,warn,...}]`, and the walker descended into option *values* as
# if they were commands. Each invented child could sprout more, and with no
# `seen` set and no depth limit the walk never finished.
_CHOICES = re.compile(r"\[-h\].*?\{([^{}]*)\}\s*(?:\.\.\.|$)", re.DOTALL)

# Commands whose help is the whole point and that spawn no work.
_LEAF_TIMEOUT = 60

# Bounds on discovery, so a scraper bug fails fast instead of hanging CI. The
# real surface is 286 paths at most 3 levels deep.
_MAX_DEPTH = 6
_MAX_PATHS = 1000


def resolve(cmd: str) -> str | None:
    """Resolve cmd to an absolute executable path.

    Windows CreateProcess only appends `.exe`, so a `cm.bat` on PATH is
    invisible to a bare subprocess spawn. shutil.which applies PATHEXT, so
    resolve once here and spawn the result.
    """
    return shutil.which(cmd)


def _child_env() -> dict:
    """A child environment with warnings suppressed.

    Paramiko emits a TripleDES deprecation warning on import under recent
    cryptography releases; it would otherwise drown the usage output we parse.
    """
    env = dict(os.environ)
    env["PYTHONWARNINGS"] = "ignore"
    env["COLUMNS"] = "200"
    env["NO_COLOR"] = "1"
    return env


def _split(path: list[str]) -> str:
    """Join a command path into a space-separated string for messages."""
    return " ".join(path)


def _usage_block(out: str) -> str:
    """Return only argparse's usage section.

    argparse repeats the subcommand list under "positional arguments:", so
    searching the whole help text would find it twice and, worse, would match
    braces belonging to an unrelated example in a command's description or
    epilog. The usage section is the `usage:` line plus its indented
    continuation lines, ending at the first blank or unindented line.
    """
    lines = out.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("usage:"):
            continue
        block = [line]
        for cont in lines[index + 1:]:
            if not cont.strip() or not cont[0].isspace():
                break
            block.append(cont)
        return "\n".join(block)
    return ""


def run_help(cmd: str, path: list[str]) -> tuple[list[str], str | None, str]:
    """Run `<cmd> <path...> --help`.

    An empty path requests top-level help. Return (subcommands, error, output),
    where output is stdout followed by stderr and error is None on success.
    No recognized subcommands means an empty list, including for leaf commands.

    A timeout after 60 seconds or a missing executable returns an error with
    empty output. A nonzero exit, traceback marker, or absence of both '-h'
    and '--help' in the output returns an error with the captured output.
    All error results have no subcommands. Other OS errors and output decoding
    errors propagate to the caller.
    """
    argv = [cmd, *path, "--help"]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_LEAF_TIMEOUT,
            env=_child_env(),
        )
    except subprocess.TimeoutExpired:
        return [], f"{_split(path)} --help timed out", ""
    except FileNotFoundError:
        return [], f"command not found: {cmd}", ""

    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return [], f"{_split(path)} --help exited {proc.returncode}", out

    # A traceback in the help output means the import chain is broken.
    if "Traceback (most recent call last)" in out:
        return [], f"{_split(path)} --help printed a traceback", out

    # A command that exits 0 without printing its flags is broken even if its
    # imports worked. This used to be a second full pass over every path, which
    # doubled the cost for no extra coverage: the walk already runs `--help` on
    # each path and has the output in hand, so assert it here instead.
    if not any(flag in out for flag in _HELP_FLAGS):
        return [], f"{_split(path)} produced no usage text", out

    match = _CHOICES.search(_usage_block(out))
    if not match:
        return [], None, out  # leaf command

    choices = [c.strip() for c in match.group(1).split(",") if c.strip()]
    # argparse lists positional-looking extras too; keep plain command names.
    return [c for c in choices if re.fullmatch(r"[A-Za-z][\w-]*", c)], None, out


def walk(cmd: str, jobs: int = 8) -> tuple[list[list[str]], list[tuple[list[str], str]]]:
    """Discover command paths through help subprocesses and return failures.

    Probe each level with up to max(1, jobs) workers. Return (paths, failures),
    where paths exclude the root invocation but include discovered paths whose
    probes fail or are skipped by a limit. Failures are (path, error) pairs;
    a top-level help failure uses an empty path and stops discovery.

    Repeated child paths are ignored. Paths with at least _MAX_DEPTH command
    words are not probed. The _MAX_PATHS budget limits probing, not the size
    of the returned path list. Hitting either limit is reported as a failure.
    Errors returned by run_help stop descent on that path; exceptions raised
    by run_help propagate to the caller.
    """
    paths: list[list[str]] = []
    failures: list[tuple[list[str], str]] = []
    seen: set[tuple[str, ...]] = set()

    top, err, _ = run_help(cmd, [])
    if err:
        failures.append(([], err))
        return paths, failures

    frontier = [[name] for name in top]
    for path in frontier:
        seen.add(tuple(path))
    paths.extend(frontier)

    while frontier:
        # Bound the level before spawning anything.
        survivors = []
        for path in frontier:
            if len(path) >= _MAX_DEPTH:
                failures.append(
                    (path, f"deeper than {_MAX_DEPTH} levels; refusing to descend")
                )
                continue
            if len(paths) + len(survivors) >= _MAX_PATHS:
                failures.append(
                    (path, f"more than {_MAX_PATHS} command paths; discovery is runaway")
                )
                break
            survivors.append(path)
        if not survivors:
            break

        def _probe(path: list[str]) -> tuple[list[str], list[str], str | None]:
            """Return the path, subcommands, and help error, if any."""
            subs, err, _ = run_help(cmd, path)
            return path, subs, err

        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            results = list(pool.map(_probe, survivors))

        frontier = []
        for path, subs, err in results:
            if err:
                failures.append((path, err))
                continue
            for sub in subs:
                child = [*path, sub]
                if tuple(child) in seen:
                    continue
                seen.add(tuple(child))
                paths.append(child)
                frontier.append(child)

    return paths, failures


def main() -> int:
    """Walk the whole CLI command surface and report any broken commands.

    Read options from sys.argv. Return 0 on success, 1 for discovery or help
    failures, or 2 if the executable cannot be resolved. Print failures to
    stderr; --quiet suppresses success summaries but not the startup message.
    Argument parsing raises SystemExit for --help or invalid arguments.
    Exceptions from walk propagate.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cmd", default="cm", help="CLI executable to exercise")
    ap.add_argument("--jobs", type=int, default=8, help="parallel workers")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    resolved = resolve(args.cmd)
    if resolved is None:
        print(f"[FAIL] {args.cmd!r} is not on PATH", file=sys.stderr)
        return 2
    args.cmd = resolved

    print(f"Smoke testing {args.cmd} ...")
    paths, failures = walk(args.cmd, jobs=args.jobs)

    if failures:
        print(f"\n{len(failures)} command(s) failed:\n", file=sys.stderr)
        for path, err in failures:
            print(f"  [FAIL] {err}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"[OK] {len(paths)} command paths respond to --help")
        print(f"[OK] {args.cmd} command surface is intact")
    return 0


if __name__ == "__main__":
    sys.exit(main())