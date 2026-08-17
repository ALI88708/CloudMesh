"""Shared fixtures for CloudMesh tests."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmp_acl(tmp_path, monkeypatch):
    """Provide a temporary ACL directory for isolated tests."""
    import core.acl as acl_mod
    monkeypatch.setattr(acl_mod, "DATA_DIR", str(tmp_path))
    return acl_mod


@pytest.fixture
def api_instance():
    """Provide a fresh CloudMeshAPI instance."""
    from core.advanced import CloudMeshAPI
    return CloudMeshAPI(api_key="test_key_for_ci_only")


@pytest.fixture
def node_agent():
    """Provide a NodeAgent bound to a random port with a test key."""
    sys.path.insert(0, str(ROOT / "node"))
    from cloudmesh_node import NodeAgent
    return NodeAgent(port=0, auth_key="test_auth_key", bind_host="127.0.0.1")
