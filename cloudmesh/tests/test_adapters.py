"""Regression tests: CLI-facing adapters exist and the node agent is standalone."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _import(name):
    """Import a cloudmesh.core module, falling back to the top-level core package."""
    try:
        module = __import__(f"cloudmesh.core.{name}", fromlist=["*"])
    except ImportError:
        module = __import__(f"core.{name}", fromlist=["*"])
    return module


def test_docker_manager_api():
    """DockerManager must expose all the methods the CLI adapter relies on."""
    mod = _import("docker")
    assert hasattr(mod, "DockerManager")
    mgr = mod.DockerManager()
    for method in ("list_servers", "list_containers", "docker_compose",
                   "container_stats", "list_images", "pull_image",
                   "exec_command", "container_logs", "cleanup", "prune"):
        assert callable(getattr(mgr, method, None)), method


def test_firewall_manager_api():
    """FirewallManager must expose all the methods the CLI adapter relies on."""
    mod = _import("firewall")
    assert hasattr(mod, "FirewallManager")
    mgr = mod.FirewallManager()
    for method in ("list_rules", "add_rule", "remove_rule", "status",
                   "check_port", "backup", "load_rules"):
        assert callable(getattr(mgr, method, None)), method


def test_ssl_checker_api():
    """SSLChecker must expose all the methods the CLI adapter relies on."""
    mod = _import("sslcheck")
    assert hasattr(mod, "SSLChecker")
    mgr = mod.SSLChecker()
    for method in ("check_domain", "check_all", "list_domains", "add_domain",
                   "remove_domain", "history", "renew_check"):
        assert callable(getattr(mgr, method, None)), method


def test_log_aggregator_api():
    """LogAggregator must expose all the methods the CLI adapter relies on."""
    mod = _import("logagg")
    assert hasattr(mod, "LogAggregator")
    mgr = mod.LogAggregator()
    for method in ("add_source", "list_sources", "search", "filter_logs",
                   "subscribe", "stats", "clear"):
        assert callable(getattr(mgr, method, None)), method


def test_firewall_ufw_parsing():
    """`_parse_ufw_rules` must parse ufw status output into rule dicts."""
    mod = _import("firewall")
    sample = "[ 1] 22/tcp ALLOW IN Anywhere\n[ 2] 443 ALLOW IN Anywhere (v6)\n"
    rules = mod._parse_ufw_rules(sample)
    assert rules[0] == {"port": "22", "protocol": "tcp", "action": "allow", "source": "*"}
    assert rules[1]["source"] == "* (v6)"
    assert mod._parse_ufw_rules("garbage output") == []


def test_main_absolute_imports_resolve():
    """Every `from cloudmesh.* import NAME` in main.py must resolve.

    Guards against handler/module API drift (e.g. missing Manager classes).
    """
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    missing = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        mod = node.module or ""
        if node.level != 0 or not mod.startswith("cloudmesh."):
            continue
        for alias in node.names:
            if alias.name == "*":
                continue
            try:
                m = __import__(mod, fromlist=[alias.name])
                getattr(m, alias.name)
            except Exception as e:
                missing.append(f"{mod}:{alias.name} ({e})")
    assert missing == []


def test_node_agent_starts_without_core_package(tmp_path):
    """Standalone agent must boot with the embedded DDoS fallback.

    Runs in a subprocess whose sys.path exposes only the node directory,
    so neither `core` nor `cloudmesh` is importable.
    """
    node_dir = ROOT / "node"
    code = (
        "import sys; sys.path.insert(0, r'" + str(node_dir) + "');"
        "from cloudmesh_node import NodeAgent;"
        "a = NodeAgent(port=0, auth_key='test-key', bind_host='127.0.0.1');"
        "print(type(a._ddos).__name__)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=60,
        env={"PATH": __import__("os").environ.get("PATH", ""),
             "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
             "PYTHONUTF8": "1"},
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert proc.stdout.strip() == "_StandaloneDDoSProtection"


def test_standalone_ddos_blocks_bruteforce():
    """The embedded DDoS fallback must ban an IP after repeated auth failures."""
    try:
        from cloudmesh.node.cloudmesh_node import _StandaloneDDoSProtection
    except ImportError:
        sys.path.insert(0, str(ROOT / "node"))
        from cloudmesh_node import _StandaloneDDoSProtection
    guard = _StandaloneDDoSProtection(ban_threshold=3, ban_duration=60)
    assert guard.check_connection("10.0.0.1")[0] is True
    guard.release_connection("10.0.0.1")
    assert guard.on_auth_failure("10.0.0.2") is False
    assert guard.on_auth_failure("10.0.0.2") is False
    assert guard.on_auth_failure("10.0.0.2") is True
    assert guard.check_connection("10.0.0.2")[0] is False
    guard.on_auth_success("10.0.0.9")
    assert guard.check_connection("10.0.0.9")[0] is True
