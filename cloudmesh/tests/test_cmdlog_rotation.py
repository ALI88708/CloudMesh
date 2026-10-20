import json

from core.cmdlog import CommandLog


def test_trimming_preserves_the_chain_and_writes_a_checkpoint(tmp_path):
    log = CommandLog(tmp_path, max_entries=3)
    for index in range(5):
        log.log(f"cmd{index}")
    result = log.verify()
    assert result["valid"] is True
    assert result["total"] == 3
    checkpoint = json.loads((tmp_path / "command_log.checkpoint.json").read_text())
    assert checkpoint["dropped"] == 2
    assert log.get_recent(1)[0]["command"] == "cmd4"


def test_editing_the_first_retained_entry_is_detected(tmp_path):
    log = CommandLog(tmp_path, max_entries=3)
    for index in range(5):
        log.log(f"cmd{index}")
    path = tmp_path / "command_log.json"
    entries = json.loads(path.read_text())
    entries[0]["command"] = "tampered"
    path.write_text(json.dumps(entries))
    assert CommandLog(tmp_path, max_entries=3).verify()["valid"] is False


def test_editing_the_checkpoint_is_detected(tmp_path):
    log = CommandLog(tmp_path, max_entries=3)
    for index in range(5):
        log.log(f"cmd{index}")
    checkpoint = tmp_path / "command_log.checkpoint.json"
    data = json.loads(checkpoint.read_text())
    data["anchor_hash"] = "0" * 64
    checkpoint.write_text(json.dumps(data))
    assert CommandLog(tmp_path, max_entries=3).verify()["valid"] is False


def test_a_legacy_truncated_log_is_anchored_at_its_first_entry(tmp_path):
    path = tmp_path / "command_log.json"
    path.write_text(json.dumps([
        {
            "timestamp": "2026-01-01T00:00:00",
            "command": "old",
            "args": "",
            "prev_hash": "a" * 64,
            "entry_hash": "b" * 64,
            "version": 2,
        }
    ]))
    result = CommandLog(tmp_path, max_entries=3).verify()
    assert result["valid"] is True
    assert result.get("legacy_truncated") is True
