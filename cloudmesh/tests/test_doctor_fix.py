"""`cm doctor --fix`: safe, backup-first repairs for what doctor reports.

Doctor used to stop at diagnosis. These tests pin the repair contract: only
problems with an obviously safe remedy are touched, a corrupt state file is
always backed up before it is reset, and a healthy file is never rewritten.
"""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as cloudmesh_main


def test_fix_creates_a_missing_data_directory(tmp_path):
    """The 'Data directory' row is fixable with a mkdir."""
    data_dir = tmp_path / "state"

    actions = cloudmesh_main._doctor_repairs(tmp_path, data_dir)

    assert data_dir.is_dir()
    assert any("data directory" in action.lower() for action in actions)


def test_fix_leaves_an_existing_data_directory_alone(tmp_path):
    """No repair is reported when there is nothing to repair."""
    data_dir = tmp_path / "state"
    data_dir.mkdir()

    actions = cloudmesh_main._doctor_repairs(tmp_path, data_dir)

    assert not any("data directory" in action.lower() for action in actions)


def test_fix_backs_up_a_corrupt_node_keys_file_before_resetting_it(tmp_path):
    """Corrupt state is preserved as .bak, never silently destroyed."""
    data_dir = tmp_path / "state"
    data_dir.mkdir()
    broken = tmp_path / ".node_keys.json"
    broken.write_text("{not json")

    actions = cloudmesh_main._doctor_repairs(tmp_path, data_dir)

    backup = tmp_path / ".node_keys.json.bak"
    assert backup.read_text() == "{not json"
    assert json.loads(broken.read_text()) == {}
    assert any(".bak" in action for action in actions)


def test_fix_backs_up_a_corrupt_schedule_file(tmp_path):
    """The same rule covers the schedule store."""
    data_dir = tmp_path / "state"
    data_dir.mkdir()
    broken = tmp_path / ".schedule.json"
    broken.write_text("]]]")

    cloudmesh_main._doctor_repairs(tmp_path, data_dir)

    assert (tmp_path / ".schedule.json.bak").read_text() == "]]]"
    assert json.loads(broken.read_text()) == {}


def test_fix_does_not_touch_a_healthy_state_file(tmp_path):
    """A valid keyring is user data, not something to reset."""
    data_dir = tmp_path / "state"
    data_dir.mkdir()
    healthy = tmp_path / ".node_keys.json"
    healthy.write_text(json.dumps({"web-1": {"key": "secret"}}))

    actions = cloudmesh_main._doctor_repairs(tmp_path, data_dir)

    assert json.loads(healthy.read_text()) == {"web-1": {"key": "secret"}}
    assert not (tmp_path / ".node_keys.json.bak").exists()
    assert not actions or all(".bak" not in action for action in actions)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits only")
def test_fix_tightens_secret_key_permissions(tmp_path):
    """A world-readable Fernet key defeats the encryption it protects."""
    data_dir = tmp_path / "state"
    data_dir.mkdir()
    key = tmp_path / ".secret.key"
    key.write_bytes(b"k" * 44)
    key.chmod(0o644)

    cloudmesh_main._doctor_repairs(tmp_path, data_dir)

    assert stat.S_IMODE(key.stat().st_mode) == 0o600


def test_the_doctor_parser_exposes_fix():
    """`cm doctor --fix` has to reach the handler."""
    parser = cloudmesh_main.build_parser()
    args = parser.parse_args(["doctor", "--fix"])

    assert args.fix is True
