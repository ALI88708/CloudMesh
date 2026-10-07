"""No command may crash with a programming error on first use.

`cm api` raised NameError because `time` was never imported. `cm panic rotate`
raised NameError on a function that did not exist. `cm panic retry-pending`
raised UnboundLocalError. `cm run "uptime"` exited 0 without doing anything.
Each shipped because nothing ever ran them.

This drives a broad slice of the command surface and fails on any Python
traceback or fatal exception. Connection refusals, missing nodes, and "no data"
messages are fine — those are the tool reporting, not the tool breaking.

The list is deliberately curated. Blocking commands (`watch`, `api`,
`interactive`), destructive ones (`storage restore`), and network-bound ones
(`update`, `discover`, `speed`) are excluded.

One subprocess runs the whole list (see cli_driver.py): a fresh interpreter per
command costs ~1.5s of paramiko import, which is too slow to keep in CI across a
Python-version matrix on two operating systems.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DRIVER = Path(__file__).resolve().parent / "cli_driver.py"

# Commands that are safe to run with no configuration and must not crash.
SAFE_COMMANDS = [
    ["--version"],
    ["version"],
    ["status"],
    ["doctor"],
    ["server", "list"],
    ["node", "list"],
    ["group", "list"],
    ["schedule", "list"],
    ["template", "list"],
    ["alias", "list"],
    ["keys", "list"],
    ["config", "list"],
    ["queue", "list"],
    ["tripwire", "list"],
    ["tripwire", "check"],
    ["panic", "shares"],
    ["panic", "retry-pending"],
    ["panic", "rotate"],
    ["panic", "--dry-run"],
    ["weather"],
    ["weather", "--learn"],
    ["trust"],
    ["cmdlog", "--verify"],
    ["reshistory", "summary"],
    ["reshistory", "snapshot"],
    ["history", "show"],
    ["docker", "list-servers"],
    ["firewall", "status"],
    ["firewall", "list-rules"],
    ["ssl", "domains"],
    ["logagg", "sources"],
    ["logagg", "stats"],
    ["webhooks", "list"],
    ["watcher", "list"],
    ["tunnel", "list"],
    ["acl", "users"],
    ["acl", "roles"],
    ["plugins", "list"],
    ["profile", "list"],
    ["migrate", "--dry-run"],
    ["migrate", "--verify"],
    ["storage", "list"],
    ["drift", "list"],
    ["drift", "check"],
    ["diagnose"],
    ["diagnose", "--json"],
    ["mon", "--local"],
    ["uptime"],
    ["disk"],
    ["who"],
    ["node", "job", "checkpoints"],
    ["node", "info", "-n", "definitely-not-a-node"],
    ["node", "test", "-n", "definitely-not-a-node"],
    ["server", "test", "-n", "definitely-not-a-server"],
]

TIMEOUT = 600

# pytest.ini sets a global 10s timeout for good reason (most tests are unit
# tests). This one boots an interpreter and walks 54 commands, so it needs room.
pytestmark_timeout = pytest.mark.timeout(TIMEOUT)


def _child_env() -> dict:
    env = dict(os.environ)
    env["PYTHONWARNINGS"] = "ignore"
    env["COLUMNS"] = "200"
    env["NO_COLOR"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


@pytestmark_timeout
def test_safe_commands_do_not_crash():
    """Every command in the sweep must fail gracefully, never with a traceback."""
    # No JSON argument: the list is long enough to hit the per-argument length
    # limit on Linux ("File name too long"), so the driver reads it from the
    # module itself.
    proc = subprocess.run(
        [sys.executable, str(DRIVER)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        cwd=str(ROOT),
        env=_child_env(),
    )

    report = (proc.stdout or "") + (proc.stderr or "")
    assert "FAIL " not in report, (
        "these commands crashed on first use:\n" + report[-4000:]
    )
    assert f"OK {len(SAFE_COMMANDS)}" in report, report[-2000:]


# Command invocations that reached a crash or a silent no-op, mapped to the
# main.py handler each must end up calling.
STUBBED_HANDLERS = {
    ("run", "echo hi"): "cmd_run",
    ("exec", "--all", "uptime"): "cmd_exec",
    ("api",): "cmd_api",
    ("watch",): "cmd_watch",
    ("weather",): "cmd_weather",
    ("panic", "rotate"): "cmd_panic",
    ("panic", "retry-pending"): "cmd_panic",
}


@pytest.mark.parametrize(
    "argv",
    [
        ["api"],
        ["watch"],
        ["weather"],
        ["panic", "rotate"],
        ["panic", "retry-pending"],
        ["run", "echo hi"],
        ["exec", "--all", "uptime"],
    ],
    ids=lambda a: " ".join(a),
)
def test_previously_broken_commands_now_dispatch(argv):
    """These reached a crash or a silent no-op; each must reach its handler.

    Asserted in-process with the handler stubbed, so the test cannot depend on
    networking or on any configuration existing.
    """
    stub_name = STUBBED_HANDLERS.get(tuple(argv))
    assert stub_name is not None, f"no stub registered for {argv}"

    import main as cloudmesh_main

    calls = []
    original = getattr(cloudmesh_main, stub_name)
    setattr(
        cloudmesh_main,
        stub_name,
        lambda args: calls.append(args),
    )
    saved = sys.argv
    sys.argv = ["cloudmesh", *argv]
    try:
        cloudmesh_main.main()
    finally:
        sys.argv = saved
        setattr(cloudmesh_main, stub_name, original)

    assert calls, f"`cm {' '.join(argv)}` never reached {stub_name}"


def test_help_is_reachable_for_every_command():
    """A broken import chain must fail on --help, before any handler runs."""
    import main as cloudmesh_main

    for argv in (
        ["api", "--help"],
        ["watch", "--help"],
        ["weather", "--help"],
        ["panic", "rotate", "--help"],
        ["node", "job", "start", "--help"],
        ["run", "--help"],
    ):
        saved = sys.argv
        sys.argv = ["cloudmesh", *argv]
        try:
            with pytest.raises(SystemExit) as exc:
                cloudmesh_main.main()
            assert exc.value.code == 0, f"`cm {' '.join(argv)} --help` exited {exc.value.code}"
        finally:
            sys.argv = saved