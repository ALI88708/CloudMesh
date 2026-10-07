"""Regression tests for commands that shipped broken.

Every test here covers a bug that reached a release: the command either exited
0 in complete silence, or raised NameError / UnboundLocalError the first time a
user ran it. The suite stayed green through all of them because nothing
exercised these paths.

The dispatch tests exist because `add_subparsers(dest="command")` shared a dest
with the positional "shell command to execute" argument, so `cm run "uptime"`
looked up ``cmds["uptime"]``, found nothing, and exited 0 without a peep.
"""

import sys

import pytest

import main as cloudmesh_main


def _run_main(monkeypatch, argv):
    """Invoke main() with argv and return whatever it raised."""
    monkeypatch.setattr(sys, "argv", ["cloudmesh"] + argv)
    with pytest.raises(SystemExit) as exc:
        cloudmesh_main.main()
    return exc.value.code


def _capture_handler(monkeypatch, name, record=None):
    """Replace a handler with a recorder and return the recorder list."""
    calls = record if record is not None else []

    def _handler(args):
        calls.append(args)

    monkeypatch.setattr(cloudmesh_main, name, _handler)
    return calls


# --- dispatch: the positional command must not overwrite the command name ---


@pytest.mark.parametrize(
    "argv, handler_name",
    [
        (["run", "echo hello"], "cmd_run"),
        (["exec", "--all", "uptime"], "cmd_exec"),
        (["group", "run", "-g", "g1", "uptime"], "cmd_groups"),
        (["node", "exec", "-n", "n1", "uptime"], "cmd_node_exec"),
    ],
)
def test_positional_command_reaches_handler(monkeypatch, argv, handler_name):
    """`cm run "cmd"` must dispatch to its handler, not exit 0 in silence."""
    calls = _capture_handler(monkeypatch, handler_name)
    monkeypatch.setattr(sys, "argv", ["cloudmesh"] + argv)

    cloudmesh_main.main()  # patched handler returns normally: no SystemExit

    assert len(calls) == 1, f"{handler_name} was never invoked for {argv}"
    assert calls[0].command == argv[-1]


def test_node_job_start_dispatches_to_job_handler(monkeypatch):
    """`cm node job start` used to print node help: job_sub shared node's dest."""
    calls = _capture_handler(monkeypatch, "cmd_node_job")
    monkeypatch.setattr(
        sys, "argv", ["cloudmesh", "node", "job", "start", "-n", "n1", "sleep 1"]
    )

    cloudmesh_main.main()

    assert len(calls) == 1, "cmd_node_job was never invoked"
    assert calls[0].job_action == "start"
    assert calls[0].command == "sleep 1"


def test_plugins_add_still_reads_the_command_flag(monkeypatch):
    """`plugins add -c` writes args.command; renaming the subparser dest must not."""
    calls = _capture_handler(monkeypatch, "cmd_plugins")
    monkeypatch.setattr(
        sys, "argv", ["cloudmesh", "plugins", "add", "-n", "demo", "-c", "echo hi"]
    )

    cloudmesh_main.main()

    assert len(calls) == 1
    assert calls[0].command == "echo hi"


def test_top_level_command_name_survives_parsing(monkeypatch):
    """The subparser destination must not be 'command' any more."""
    seen = []
    _capture_handler(monkeypatch, "cmd_run", seen)
    monkeypatch.setattr(sys, "argv", ["cloudmesh", "run", "uptime"])

    cloudmesh_main.main()

    assert seen[0].cmd_name == "run"
    assert seen[0].command == "uptime"


# --- dispatch: unknown names must fail loudly ---


def test_lookup_handler_reports_a_missing_entry(capsys):
    """A name in the parser but absent from the table must not exit 0."""
    with pytest.raises(SystemExit) as exc:
        cloudmesh_main._lookup_handler({}, "bogus")

    assert exc.value.code == 1
    assert "Unknown command: bogus" in capsys.readouterr().out


def test_lookup_handler_returns_the_registered_callable():
    def _handler():
        return None

    assert cloudmesh_main._lookup_handler({"run": _handler}, "run") is _handler


@pytest.mark.parametrize("argv", [["server"], ["node"], ["queue"]])
def test_group_without_a_subcommand_prints_help(monkeypatch, argv, capsys):
    """`cm server` with no subcommand hit the dispatch fallback, which took no
    arguments and raised TypeError."""
    monkeypatch.setattr(sys, "argv", ["cloudmesh"] + argv)

    cloudmesh_main.main()

    out = capsys.readouterr().out
    assert f"usage: cloudmesh {argv[0]}" in out


# --- crashes on first use ---


def test_cmd_api_reaches_its_sleep_loop(monkeypatch, capsys):
    """`cm api` raised NameError: time was never imported."""
    class _FakeAPI:
        api_key = "fake-key"

        def __init__(self, *a, **k):
            pass

        def start(self):
            return 8123

    monkeypatch.setattr(cloudmesh_main, "CloudMeshAPI", _FakeAPI)
    monkeypatch.setattr(cloudmesh_main, "_load_node_keys", lambda: {})
    monkeypatch.setattr(cloudmesh_main, "init_components", lambda: tuple([None] * 11))

    def _interrupt(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(cloudmesh_main.time, "sleep", _interrupt)
    monkeypatch.setattr(
        sys, "argv", ["cloudmesh", "api", "--port", "8123"]
    )

    cloudmesh_main.main()

    out = capsys.readouterr().out
    assert "API running on http://127.0.0.1:8123" in out
    assert "fake-key" in out
    assert "API stopped" in out


def test_cmd_weather_forecast_has_no_undefined_names(monkeypatch, capsys):
    """`cm weather` forecast paths raised NameError: datetime was never imported."""
    class _FakeWeather:
        def __init__(self, *a, **k):
            pass

        def predict_all(self, hour=None):
            return {
                "srv1": {
                    "status": "predicted",
                    "cpu_ema": 42.0,
                    "ram_ema": 51.0,
                    "samples": 7,
                }
            }

    monkeypatch.setattr(cloudmesh_main, "WeatherForecast", _FakeWeather)
    monkeypatch.setattr(
        sys, "argv", ["cloudmesh", "weather"]
    )

    cloudmesh_main.main()

    out = capsys.readouterr().out
    assert "srv1" in out
    assert "42.0%" in out


def test_panic_rotate_does_not_call_missing_load_config(monkeypatch, capsys):
    """`cm panic rotate` raised NameError: _load_config never existed."""
    monkeypatch.setattr(
        cloudmesh_main, "PanicManager",
        lambda *a, **k: _StubPanic(rotate_node_keys=["Rotated 'n1' — confirmed remotely"]),
    )
    monkeypatch.setattr(sys, "argv", ["cloudmesh", "panic", "rotate"])

    cloudmesh_main.main()

    assert "confirmed remotely" in capsys.readouterr().out


def test_panic_retry_pending_is_not_an_unbound_local(monkeypatch, capsys):
    """`cm panic retry-pending` raised UnboundLocalError on `panic`."""
    monkeypatch.setattr(
        cloudmesh_main, "PanicManager",
        lambda *a, **k: _StubPanic(retry_pending=["Retry SUCCESS: 'n1' rotated remotely"]),
    )
    monkeypatch.setattr(sys, "argv", ["cloudmesh", "panic", "retry-pending"])

    cloudmesh_main.main()

    assert "Retry SUCCESS" in capsys.readouterr().out


def test_panic_dry_run_runs(monkeypatch, capsys):
    monkeypatch.setattr(
        cloudmesh_main, "PanicManager",
        lambda *a, **k: _StubPanic(dry_run=[("rotate_secret_key", "Will generate new Fernet key")]),
    )
    monkeypatch.setattr(sys, "argv", ["cloudmesh", "panic", "--dry-run"])

    cloudmesh_main.main()

    assert "No changes made" in capsys.readouterr().out


class _StubPanic:
    def __init__(self, **results):
        self._results = results

    def rotate_node_keys(self):
        return self._results.get("rotate_node_keys", [])

    def retry_pending(self):
        return self._results.get("retry_pending", [])

    def dry_run(self):
        return self._results.get("dry_run", [])

    def execute_panic(self):
        return self._results.get("execute_panic", [])


# --- doctor checks ---


def test_doctor_ssh_checks_pass_against_the_real_module(monkeypatch, capsys):
    """The SSH checks grepped for 'MITMWarning'; the class is SSHWarning, so
    they always reported FAIL."""
    monkeypatch.setattr(
        sys, "argv", ["cloudmesh", "doctor"]
    )

    cloudmesh_main.cmd_doctor(_Args())

    out = capsys.readouterr().out
    assert "SSH: centralized" in out
    assert "SSH: centralized" in out and "| FAIL" not in _row_for(out, "SSH: centralized")
    assert "SSH: strict host keys" in out
    assert "| FAIL" not in _row_for(out, "SSH: strict host keys")


def _row_for(output, label):
    """Return the doctor table row whose first cell is label."""
    for line in output.splitlines():
        if label in line:
            return line
    raise AssertionError(f"doctor row {label!r} not found in output")


class _Args:
    base_dir = None


# --- module hygiene ---


def test_main_has_no_dynamic_import_hacks():
    """__import__("time")/("datetime") hid missing module-level imports."""
    source = cloudmesh_main.__file__
    text = open(source, encoding="utf-8").read()
    assert "__import__(" not in text, (
        "dynamic __import__() calls hide missing module-level imports"
    )


def test_time_and_datetime_are_imported_at_module_scope():
    """These were used but never imported, which is what broke cm api/weather."""
    assert hasattr(cloudmesh_main, "time"), "main must import time at module scope"
    assert cloudmesh_main.time.sleep.__module__ == "time"
    from datetime import datetime as _dt

    assert cloudmesh_main.datetime is _dt