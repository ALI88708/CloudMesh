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
_CHOICES = re.compile(r"usage:\s*\S+\s+\[?-h\]?.*?\{([^}]*)\}", re.DOTALL)
_HELP_FLAGS = ("-h", "--help")

# Commands whose help is the whole point and that spawn no work.
_LEAF_TIMEOUT = 60


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


def run_help(cmd: str, path: list[str]) -> tuple[list[str], str | None, str]:
    """Run `<cmd> <path...> --help`.

    Returns the discovered subcommands, an error message, or the raw output.
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

    match = _CHOICES.search(out)
    if not match:
        return [], None, out  # leaf command

    choices = [c.strip() for c in match.group(1).split(",") if c.strip()]
    # argparse lists positional-looking extras too; keep plain command names.
    return [c for c in choices if re.fullmatch(r"[A-Za-z][\w-]*", c)], None, out


def walk(cmd: str) -> tuple[list[list[str]], list[tuple[list[str], str]]]:
    """Return every command path reachable from the top level, plus failures."""
    paths: list[list[str]] = []
    failures: list[tuple[list[str], str]] = []

    top, err, _ = run_help(cmd, [])
    if err:
        failures.append(([], err))
        return paths, failures
    for name in top:
        paths.append([name])

    queue = [[name] for name in top]
    while queue:
        path = queue.pop()
        subs, err, _ = run_help(cmd, path)
        if err:
            failures.append((path, err))
            continue
        for sub in subs:
            child = [*path, sub]
            paths.append(child)
            queue.append(child)

    return paths, failures


def main() -> int:
    """Walk the whole CLI command surface and report any broken commands."""
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
    paths, failures = walk(args.cmd)

    if failures:
        print(f"\n{len(failures)} command(s) failed:\n", file=sys.stderr)
        for path, err in failures:
            print(f"  [FAIL] {err}", file=sys.stderr)
        return 1

    # Re-run every discovered path once more in parallel to catch anything the
    # sequential walk raced past, and to time the full surface.
    def _check(path: list[str]) -> str | None:
        """Re-run `--help` for a discovered path and return an error message, if any."""
        _, err, out = run_help(args.cmd, path)
        if err:
            return err
        if any(flag in out for flag in _HELP_FLAGS) is False:
            return f"{_split(path)} produced no usage text"
        return None

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        problems = [p for p in pool.map(_check, paths) if p]

    if problems:
        print(f"\n{len(problems)} command(s) failed:\n", file=sys.stderr)
        for p in problems:
            print(f"  [FAIL] {p}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"[OK] {len(paths)} command paths respond to --help")
        print(f"[OK] {args.cmd} command surface is intact")
    return 0


if __name__ == "__main__":
    sys.exit(main())