"""Driver: run many `cm` commands in one process and report the broken ones.

Spawning a fresh interpreter per command costs ~1.5s of paramiko import, which
made the traceback sweep too slow to keep in CI across a Python-version matrix.
This runs the whole list in a single interpreter instead.

Prints one ``FAIL <json>`` line per command that raised an unhandled
exception. A clean run prints ``OK <count>``.
"""

from __future__ import annotations

import io
import json
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Exceptions that mean our code is broken rather than the environment being
# unable/unconfigured.
FATAL = (
    NameError,
    AttributeError,
    UnboundLocalError,
    TypeError,
    ImportError,
    ModuleNotFoundError,
    SyntaxError,
    IndentationError,
    KeyError,
    RecursionError,
    ZeroDivisionError,
    IndexError,
)


def run_one(argv: list[str]) -> str | None:
    """Run one command; return a failure description or None on success."""
    import main as cloudmesh_main

    saved_argv = sys.argv
    sys.argv = ["cloudmesh", *argv]
    sink = io.StringIO()
    try:
        with redirect_stdout(sink), redirect_stderr(sink):
            cloudmesh_main.main()
    except SystemExit:
        return None  # a deliberate exit code is not a crash
    except FATAL as exc:
        return "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )[-2000:]
    except Exception as exc:  # noqa: BLE001 - report anything unexpected
        return "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )[-2000:]
    finally:
        sys.argv = saved_argv

    text = sink.getvalue()
    if "Traceback (most recent call last)" in text:
        return text[-2000:]
    return None


def main() -> int:
    verbose = "--verbose" in sys.argv
    commands = json.loads(sys.argv[1])
    failures = []
    for argv in commands:
        if verbose:
            print(f"--> cm {' '.join(argv)}", file=sys.stderr, flush=True)
        problem = run_one(argv)
        if problem:
            failures.append((argv, problem))

    for argv, problem in failures:
        print(f"FAIL {json.dumps(argv)}")
        print(problem)

    print(f"{'OK' if not failures else 'FAILED'} {len(commands) - len(failures)}/{len(commands)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())