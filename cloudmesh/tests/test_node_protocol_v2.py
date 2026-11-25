"""Node protocol replay protection and single-node key rotation.

The 4.1.2 audit deferred two gaps to a feature line: the node TCP protocol
accepted a captured request verbatim (no replay cache), and the only way to
rotate a node's auth key was a fleet-wide panic that also rotated the Fernet
key and made every stored password undecryptable. These tests pin the fix:
authenticated requests carry a nonce and a timestamp, and one node can be
rotated on its own.
"""

import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "node"))

import cloudmesh_node
from core.node_client import NodeClient
from core.panic import PanicManager


def _agent(require_nonce=True):
    """Build an agent without touching its on-disk state."""
    agent = cloudmesh_node.NodeAgent.__new__(cloudmesh_node.NodeAgent)
    agent.require_nonce = require_nonce
    agent._request_nonces = cloudmesh_node.OrderedDict()
    agent._request_nonce_lock = threading.Lock()
    return agent


def _request(nonce="abc123", timestamp=None, auth="k"):
    """Return a request shaped like the ones NodeClient sends."""
    return {
        "action": "ping",
        "auth": auth,
        "nonce": nonce,
        "timestamp": time.time() if timestamp is None else timestamp,
    }


# --- replay protection ------------------------------------------------------


def test_a_replayed_nonce_is_rejected():
    """The same captured request must not execute twice."""
    agent = _agent()
    request = _request()

    assert agent._check_request_replay(request) is None
    second = agent._check_request_replay(request)

    assert second is not None
    assert "replay" in second.lower()


def test_a_stale_timestamp_is_rejected_before_the_nonce_is_stored():
    """An old request is replayable by definition; it must not burn a nonce."""
    agent = _agent()
    stale = _request(timestamp=time.time() - 3600)

    error = agent._check_request_replay(stale)

    assert error is not None
    assert "stale" in error.lower()
    assert not agent._request_nonces


def test_a_fresh_nonce_after_a_stale_one_still_works():
    """A rejected stale packet must not block the client's next request."""
    agent = _agent()
    agent._check_request_replay(_request(timestamp=time.time() - 3600))

    assert agent._check_request_replay(_request()) is None


def test_legacy_clients_are_rejected_by_default_in_v5():
    """CloudMesh 5 makes replay protection mandatory on new agents."""
    agent = _agent()

    error = agent._check_request_replay({"action": "ping", "auth": "k"})

    assert error is not None
    assert "nonce" in error.lower()


def test_allow_legacy_restores_the_4_x_compatibility_mode():
    """`--allow-legacy` is the explicit migration escape hatch."""
    agent = _agent(require_nonce=False)

    assert agent._check_request_replay({"action": "ping", "auth": "k"}) is None


def test_partial_replay_fields_are_rejected():
    """A nonce without a timestamp cannot be age-checked, so it is invalid."""
    agent = _agent()

    assert agent._check_request_replay({"action": "ping", "nonce": "x", "timestamp": None}) is not None
    assert agent._check_request_replay({"action": "ping", "timestamp": time.time()}) is not None


def test_nonce_cache_evicts_oldest_first():
    """A busy node must not evict the nonces that matter most."""
    agent = _agent()
    for index in range(10001):
        agent._check_request_replay(_request(nonce=f"n{index}"))

    assert len(agent._request_nonces) == 10000
    assert "n0" not in agent._request_nonces
    assert "n10000" in agent._request_nonces


def test_v5_start_requires_nonces_unless_allow_legacy_is_passed(monkeypatch):
    """The agent CLI exposes the migration escape hatch explicitly."""
    calls = []
    monkeypatch.setattr(
        cloudmesh_node, "cmd_start", lambda **kwargs: calls.append(kwargs)
    )

    monkeypatch.setattr(sys, "argv", ["cloudmesh_node.py", "start"])
    cloudmesh_node.main()
    monkeypatch.setattr(
        sys, "argv", ["cloudmesh_node.py", "start", "--allow-legacy"]
    )
    cloudmesh_node.main()

    assert calls[0]["require_nonce"] is True
    assert calls[1]["require_nonce"] is False


# --- controller stamping ----------------------------------------------------


def test_client_stamps_every_request_with_a_fresh_nonce():
    """Two sends of the same command must not share a nonce."""
    first = NodeClient._stamp_request({"action": "ping", "auth": "k"})
    second = NodeClient._stamp_request({"action": "ping", "auth": "k"})

    assert first["nonce"] != second["nonce"]
    assert abs(time.time() - first["timestamp"]) < 5


def test_client_stamping_does_not_mutate_the_caller_request():
    """The request dict belongs to the caller; stamping returns a copy."""
    original = {"action": "ping", "auth": "k"}

    stamped = NodeClient._stamp_request(original)

    assert "nonce" not in original
    assert stamped is not original


# --- single-node rotation ---------------------------------------------------


class _Keyring:
    def __init__(self, nodes):
        """Store the node keyring in memory."""
        self.nodes = nodes
        self.saved = None

    def load(self):
        """Return the current nodes."""
        return dict(self.nodes)

    def save(self, nodes):
        """Record the save and update the stored nodes."""
        self.saved = dict(nodes)
        self.nodes = dict(nodes)


class _FakeClient:
    def __init__(self, result):
        """Return a canned rotate_key response."""
        self.result = result
        self.rotated = None

    def rotate_key(self, new_key):
        """Record the requested key and return the canned response."""
        self.rotated = new_key
        return self.result


def _manager(tmp_path, nodes, monkeypatch, result):
    """Build a PanicManager whose remote client is a fake."""
    manager = PanicManager(base_dir=tmp_path, keyring=_Keyring(nodes))
    client = _FakeClient(result)
    factory = staticmethod(lambda info, name=None: client)
    # The suite imports `core.node_client` while the product imports
    # `cloudmesh.core.node_client`; Python loads the file as two modules, so
    # both copies of the class need the fake.
    monkeypatch.setattr(NodeClient, "from_config", factory)
    import cloudmesh.core.node_client as packaged_client

    monkeypatch.setattr(packaged_client.NodeClient, "from_config", factory)
    return manager, client


def test_single_node_rotation_updates_only_that_node(tmp_path, monkeypatch):
    """A targeted rotation must not touch the other nodes' keys."""
    nodes = {
        "web-1": {"host": "h1", "port": 9999, "key": "old-1"},
        "web-2": {"host": "h2", "port": 9999, "key": "old-2"},
    }
    manager, client = _manager(tmp_path, nodes, monkeypatch, {"success": True})

    actions = manager.rotate_single_node("web-1")

    saved = manager.keyring.saved
    assert saved["web-1"]["key"] == client.rotated
    assert len(client.rotated) == 64
    assert saved["web-2"]["key"] == "old-2"
    assert not (tmp_path / ".panic_pending.json").exists()
    assert any("web-1" in action for action in actions)


def test_single_node_rotation_queues_an_unreachable_node(tmp_path, monkeypatch):
    """An offline node must be retryable, not silently dropped."""
    nodes = {"web-1": {"host": "h1", "port": 9999, "key": "old-1"}}
    manager, client = _manager(
        tmp_path, nodes, monkeypatch, {"success": False, "message": "unreachable"}
    )

    actions = manager.rotate_single_node("web-1")

    assert manager.keyring.saved is None
    pending = json.loads((tmp_path / ".panic_pending.json").read_text())
    assert pending["web-1"]["old_key"] == "old-1"
    assert pending["web-1"]["new_key"] == client.rotated
    assert any("PENDING" in action for action in actions)


def test_single_node_rotation_rejects_an_unknown_node(tmp_path, monkeypatch):
    """Rotating a typo must fail loudly instead of creating a new entry."""
    manager, _ = _manager(tmp_path, {}, monkeypatch, {"success": True})

    with pytest.raises(KeyError):
        manager.rotate_single_node("nope")


def test_rotate_key_command_exits_nonzero_when_rotation_is_pending(
    tmp_path, monkeypatch, capsys
):
    """An unconfirmed rotation is not a success."""
    import main as cloudmesh_main

    nodes = {"web-1": {"host": "h1", "port": 9999, "key": "old-1"}}
    manager, _ = _manager(tmp_path, nodes, monkeypatch, {"success": False})
    monkeypatch.setattr(cloudmesh_main, "PanicManager", lambda: manager)

    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_node_rotate_key(SimpleNamespace(name="web-1"))

    assert exc_info.value.code == 1
    assert "PENDING" in capsys.readouterr().out


def test_rotate_key_command_reports_success(tmp_path, monkeypatch, capsys):
    """A confirmed rotation prints the node name and exits normally."""
    import main as cloudmesh_main

    nodes = {"web-1": {"host": "h1", "port": 9999, "key": "old-1"}}
    manager, _ = _manager(tmp_path, nodes, monkeypatch, {"success": True})
    monkeypatch.setattr(cloudmesh_main, "PanicManager", lambda: manager)

    cloudmesh_main.cmd_node_rotate_key(SimpleNamespace(name="web-1"))

    assert "web-1" in capsys.readouterr().out


def test_rotate_key_command_rejects_unknown_node(tmp_path, monkeypatch, capsys):
    """The CLI surfaces the KeyError as a clean error, not a traceback."""
    import main as cloudmesh_main

    manager, _ = _manager(tmp_path, {}, monkeypatch, {"success": True})
    monkeypatch.setattr(cloudmesh_main, "PanicManager", lambda: manager)

    with pytest.raises(SystemExit) as exc_info:
        cloudmesh_main.cmd_node_rotate_key(SimpleNamespace(name="nope"))

    assert exc_info.value.code == 1


def test_the_node_parser_exposes_rotate_key():
    """`cm node rotate-key -n NAME` has to reach the handler."""
    import main as cloudmesh_main

    parser = cloudmesh_main.build_parser()
    args = parser.parse_args(["node", "rotate-key", "-n", "web-1"])

    assert args.action == "rotate-key"
    assert args.name == "web-1"
