"""Isolated regression tests for help discovery; no CLI processes are started."""

import subprocess
import sys
from collections import Counter
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import smoke_cli  # noqa: E402


@pytest.fixture
def help_process(monkeypatch):
    process = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(smoke_cli.subprocess, "run", process)
    return process


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        ("usage: cm logagg filter [-h] [--level {error,warn,info}]", []),
        ("usage: cm webhooks add [-h] --type {discord,slack,custom} --url URL", []),
        ("usage: cm leaf [-h] {input} OUTPUT", []),
        ("usage: cm node [-h] {add,remove,list} ...", ["add", "remove", "list"]),
        (
            "usage: cm node job [-h] [--level {error,warn}]\n"
            "                   {start,\n                    status} ...",
            ["start", "status"],
        ),
        ("usage: cm node [-h] {add,list}\n                   ...", ["add", "list"]),
        ("usage: cm node [-h] {add,list}", ["add", "list"]),
        ("usage: cm [-h] { add-source, ,list_nodes,0bad,--flag,a/b } ...",
         ["add-source", "list_nodes"]),
    ],
    ids=["option-choices", "required-option", "positional-metavar", "subcommands",
         "wrapped-choices-after-option", "wrapped-ellipsis", "end-of-usage",
         "plain-command-names"],
)
def test_run_help_discovers_only_command_choices(help_process, usage, expected):
    output = usage + "\n\noptions:\n  -h, --help  show this help message\n"
    help_process.return_value.stdout = output

    assert smoke_cli.run_help("cm", ["node"]) == (expected, None, output)


def test_run_help_ignores_subcommand_examples_outside_usage(help_process):
    output = (
        "usage: cm leaf [-h] [--level {error,warn}]\n\n"
        "Example: cm [-h] {invented,children} ...\n"
    )
    help_process.return_value.stdout = output

    assert smoke_cli.run_help("cm", ["leaf"]) == ([], None, output)


@pytest.mark.parametrize("output", ["", "operation completed\n", "usage: cm node\n"])
@pytest.mark.parametrize("path", [[], ["node", "list"]], ids=["root", "nested"])
def test_run_help_rejects_success_without_help_flags(help_process, output, path):
    help_process.return_value.stdout = output

    children, error, captured = smoke_cli.run_help("cm", path)

    assert children == []
    assert error == f"{' '.join(path)} produced no usage text"
    assert captured == output


@pytest.mark.parametrize("flag", ["-h", "--help"])
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_run_help_accepts_either_help_flag_on_either_stream(help_process, flag, stream):
    output = f"options:\n  {flag}  show this help message\n"
    setattr(help_process.return_value, stream, output)

    assert smoke_cli.run_help("cm", []) == ([], None, output)


@pytest.mark.parametrize(
    ("returncode", "stderr", "message"),
    [
        (2, "invalid command", "exited 2"),
        (0, "Traceback (most recent call last):\nimport failed", "printed a traceback"),
    ],
)
def test_run_help_errors_do_not_advertise_children(
    help_process, returncode, stderr, message,
):
    stdout = "usage: cm node [-h] {add,list} ...\n"
    help_process.return_value = subprocess.CompletedProcess([], returncode, stdout, stderr)

    assert smoke_cli.run_help("cm", ["node"]) == (
        [], f"node --help {message}", stdout + stderr,
    )


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (subprocess.TimeoutExpired("cm", 60), "node --help timed out"),
        (FileNotFoundError("missing"), "command not found: cm"),
    ],
)
def test_run_help_reports_process_failures(help_process, exception, message):
    help_process.side_effect = exception

    assert smoke_cli.run_help("cm", ["node"]) == ([], message, "")


@pytest.fixture
def help_tree(monkeypatch):
    def install(tree, errors=None):
        errors = errors or {}

        def probe(cmd, path):
            key = tuple(path)
            return tree[key], errors.get(key), ""

        probe_mock = Mock(side_effect=probe)
        monkeypatch.setattr(smoke_cli, "run_help", probe_mock)
        return probe_mock

    return install


def _visited(probe):
    return Counter(tuple(call.args[1]) for call in probe.call_args_list)


def test_walk_deduplicates_siblings_but_preserves_distinct_parent_paths(help_tree):
    tree = {
        (): ["node", "server"],
        ("node",): ["list", "list", "add", "list"],
        ("server",): ["list", "list"],
        ("node", "list"): [],
        ("node", "add"): [],
        ("server", "list"): [],
    }
    probe = help_tree(tree)

    paths, failures = smoke_cli.walk("cm", jobs=2)

    assert failures == []
    assert Counter(map(tuple, paths)) == Counter({path: 1 for path in tree if path})
    assert _visited(probe) == Counter({path: 1 for path in tree})


def test_walk_root_failure_stops_discovery(help_tree):
    probe = help_tree({(): ["ignored"]}, {(): "root produced no usage text"})

    assert smoke_cli.walk("cm") == ([], [([], "root produced no usage text")])
    assert _visited(probe) == Counter({(): 1})


def test_walk_leaf_root_is_valid(help_tree):
    probe = help_tree({(): []})

    assert smoke_cli.walk("cm") == ([], [])
    assert _visited(probe) == Counter({(): 1})


def test_walk_retains_failed_paths_and_continues_healthy_branches(help_tree):
    tree = {
        (): ["broken", "healthy", "also-broken"],
        ("broken",): ["ignored"],
        ("healthy",): ["list"],
        ("also-broken",): [],
        ("healthy", "list"): [],
    }
    errors = {("broken",): "no usage text", ("also-broken",): "timed out"}
    probe = help_tree(tree, errors)

    paths, failures = smoke_cli.walk("cm", jobs=2)

    assert {tuple(path) for path in paths} == set(tree) - {()}
    assert {tuple(path): error for path, error in failures} == errors
    assert _visited(probe) == Counter({path: 1 for path in tree})


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_walk_reports_depth_boundary_without_probing_it(monkeypatch, help_tree, depth):
    monkeypatch.setattr(smoke_cli, "_MAX_DEPTH", depth)
    tree = {("child",) * level: ["child"] for level in range(depth)}
    probe = help_tree(tree)

    paths, failures = smoke_cli.walk("cm")

    assert paths == [["child"] * level for level in range(1, depth + 1)]
    assert len(failures) == 1
    assert failures[0][0] == ["child"] * depth
    assert "refusing to descend" in failures[0][1]
    assert _visited(probe) == Counter({path: 1 for path in tree})


@pytest.mark.parametrize("width", [3, 4])
def test_walk_reports_path_budget_at_or_above_limit(monkeypatch, help_tree, width):
    monkeypatch.setattr(smoke_cli, "_MAX_PATHS", 3)
    names = [f"command{index}" for index in range(width)]
    probe = help_tree({(): names})

    paths, failures = smoke_cli.walk("cm")

    assert paths == [[name] for name in names]
    assert failures and "discovery is runaway" in failures[0][1]
    assert _visited(probe) == Counter({(): 1})


def test_walk_completes_below_path_budget(monkeypatch, help_tree):
    monkeypatch.setattr(smoke_cli, "_MAX_PATHS", 3)
    probe = help_tree({(): ["node"], ("node",): ["list"], ("node", "list"): []})

    assert smoke_cli.walk("cm") == ([["node"], ["node", "list"]], [])
    assert _visited(probe) == Counter({(): 1, ("node",): 1, ("node", "list"): 1})


@pytest.mark.parametrize("jobs", [-2, 0, 1])
def test_walk_uses_at_least_one_worker(help_tree, jobs):
    probe = help_tree({(): ["node"], ("node",): []})

    assert smoke_cli.walk("cm", jobs=jobs) == ([["node"]], [])
    assert _visited(probe) == Counter({(): 1, ("node",): 1})


def test_walk_probes_siblings_concurrently(monkeypatch):
    rendezvous = Barrier(2, timeout=5)

    def probe(cmd, path):
        if not path:
            return ["node", "server"], None, ""
        rendezvous.wait()
        return [], None, ""

    monkeypatch.setattr(smoke_cli, "run_help", probe)

    paths, failures = smoke_cli.walk("cm", jobs=2)

    assert {tuple(path) for path in paths} == {("node",), ("server",)}
    assert failures == []


def test_walk_propagates_worker_exceptions(monkeypatch):
    probe = Mock(side_effect=[(["node"], None, ""), PermissionError("denied")])
    monkeypatch.setattr(smoke_cli, "run_help", probe)

    with pytest.raises(PermissionError, match="denied"):
        smoke_cli.walk("cm")


@pytest.mark.parametrize("quiet", [False, True])
def test_main_checks_each_path_once_and_forwards_jobs(monkeypatch, help_tree, capsys, quiet):
    probe = help_tree({(): ["node"], ("node",): ["list"], ("node", "list"): []})
    walk = Mock(wraps=smoke_cli.walk)
    monkeypatch.setattr(smoke_cli, "walk", walk)
    resolve = Mock(return_value="/fake/bin/cm")
    monkeypatch.setattr(smoke_cli, "resolve", resolve)
    argv = ["smoke_cli.py", "--cmd", "custom-cm", "--jobs", "2"]
    monkeypatch.setattr(sys, "argv", argv + (["--quiet"] if quiet else []))

    assert smoke_cli.main() == 0

    resolve.assert_called_once_with("custom-cm")
    walk.assert_called_once_with("/fake/bin/cm", jobs=2)
    assert _visited(probe) == Counter({(): 1, ("node",): 1, ("node", "list"): 1})
    assert all(call.args[0] == "/fake/bin/cm" for call in probe.call_args_list)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Smoke testing /fake/bin/cm" in captured.out
    if quiet:
        assert "[OK]" not in captured.out
    else:
        assert "[OK] 2 command paths respond to --help" in captured.out
        assert "[OK] /fake/bin/cm command surface is intact" in captured.out


@pytest.mark.parametrize("broken_path", [(), ("node",)], ids=["root", "child"])
def test_main_reports_missing_usage_during_discovery(
    monkeypatch, help_process, capsys, broken_path,
):
    def process(argv, **kwargs):
        path = tuple(argv[1:-1])
        output = "done" if path == broken_path else "usage: cm [-h] {node} ...\n"
        return subprocess.CompletedProcess(argv, 0, output, "")

    help_process.side_effect = process
    monkeypatch.setattr(smoke_cli, "resolve", lambda cmd: "/fake/bin/cm")
    monkeypatch.setattr(sys, "argv", ["smoke_cli.py", "--quiet"])

    assert smoke_cli.main() == 1

    captured = capsys.readouterr()
    assert "1 command(s) failed" in captured.err
    assert "produced no usage text" in captured.err
    assert "[OK]" not in captured.out
    assert help_process.call_count == (1 if not broken_path else 2)
