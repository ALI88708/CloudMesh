"""The behaviours that decide whether a bad day becomes data loss.

Every test here injects a real fault -- a full disk, a truncated file, a
second worker, a dead ssh process -- and asserts one of two outcomes: the
correct result, or a named failure. What must never happen is a silent
success, because that is the failure mode a user cannot see and cannot
recover from.

The contracts pinned here:

1. A write that fails half way leaves the previous file untouched. `os.replace`
   is atomic, so the only way to lose the old config is to write in place.
2. A file that exists and cannot be read is reported. Returning defaults makes
   a corrupt config look like a fresh install, and the next save then
   overwrites the only copy of the data.
3. The command ledger is append-only. A log that cannot be parsed must not be
   silently replaced by a new chain, because that erases the evidence the
   ledger exists to preserve.
4. Concurrent writers keep the chain verifiable. The ledger rewrites the whole
   list on every append, so two threads that read-modify-write it at once drop
   entries.
"""

import errno
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloudmesh.core import ssh_util  # noqa: E402
from cloudmesh.core.cmdlog import CommandLog  # noqa: E402
from cloudmesh.core.drain import DrainRegistry  # noqa: E402
from cloudmesh.core.security import SecurityManager, config_health  # noqa: E402
from cloudmesh.core.task_queue import (  # noqa: E402
    SmartTaskQueue,
    WorkerAlreadyRunningError,
)


def _disk_full(*args, **kwargs):
    raise OSError(errno.ENOSPC, "No space left on device")


def test_a_failed_replace_keeps_the_previous_config(tmp_path, monkeypatch):
    """A full disk at commit time must not cost the user their servers.

    The encrypted config is written to a temporary file and moved into place.
    If that move fails, the old file has to still be there and still decrypt;
    anything else means a failed save destroyed the working install.
    """
    manager = SecurityManager(base_dir=tmp_path)
    manager.save_config({"servers": {"keep": {"host": "10.0.0.1"}}, "settings": {}})
    before = manager.config_path.read_bytes()

    monkeypatch.setattr("cloudmesh.core.security.os.replace", _disk_full)
    with pytest.raises(OSError):
        manager.save_config({"servers": {"new": {"host": "10.0.0.2"}}, "settings": {}})

    assert manager.config_path.read_bytes() == before
    assert SecurityManager(base_dir=tmp_path).load_config()["servers"] == {
        "keep": {"host": "10.0.0.1"}
    }


def test_a_write_that_dies_mid_stream_leaves_no_partial_file(tmp_path, monkeypatch):
    """A half-written temp file must not survive as debris or as the config."""
    manager = SecurityManager(base_dir=tmp_path)
    manager.save_config({"servers": {"keep": {"host": "10.0.0.1"}}, "settings": {}})
    before = manager.config_path.read_bytes()

    real_named_temporary_file = tempfile.NamedTemporaryFile

    class _FailingFile:
        def __init__(self, real):
            self._real = real
            self.name = real.name

        def write(self, data):
            self._real.write(data[: max(1, len(data) // 2)])
            raise OSError(errno.ENOSPC, "No space left on device")

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            self._real.close()
            return False

    monkeypatch.setattr(
        "cloudmesh.core.security.tempfile.NamedTemporaryFile",
        lambda *a, **k: _FailingFile(real_named_temporary_file(*a, **k)),
    )
    with pytest.raises(OSError):
        manager.save_config({"servers": {"new": {"host": "10.0.0.2"}}, "settings": {}})

    assert manager.config_path.read_bytes() == before
    assert list(tmp_path.glob(".config.json.*.tmp")) == []


def test_a_corrupt_config_is_reported_instead_of_looking_empty(tmp_path):
    """Defaults for a missing file are fine; defaults for a broken one are not.

    `load_config` cannot refuse to start, but it has to leave a trace: the
    caller that shows an empty server list is otherwise indistinguishable from
    a user who never added a server.
    """
    manager = SecurityManager(base_dir=tmp_path)
    manager.config_path.write_bytes(b"this is not a fernet token")

    config = SecurityManager(base_dir=tmp_path).load_config()
    reloaded = SecurityManager(base_dir=tmp_path)
    reloaded.load_config()

    assert config["servers"] == {}
    assert reloaded.last_load_error, "the corrupt config was swallowed silently"
    assert "config" in reloaded.last_load_error.lower()

    ok, detail = config_health(tmp_path)
    assert ok is False
    assert "config" in detail.lower()


def test_the_config_health_probe_creates_nothing(tmp_path):
    """`cm doctor` must not create the data directory it is reporting on.

    A health check that mkdirs the path it was asked to inspect turns a failed
    row into a passing one on the next run, and writes to a directory the user
    may have pointed at by mistake.
    """
    target = tmp_path / "missing-data-dir"

    ok, detail = config_health(target)

    assert ok is True
    assert "no config" in detail
    assert not target.exists(), "the doctor's config probe created the data directory"


def test_a_corrupt_ledger_is_not_reported_as_a_valid_empty_log(tmp_path):
    """An unreadable chain is evidence of damage, not an empty chain."""
    log = CommandLog(base_dir=tmp_path)
    log.log("uptime")
    log.log_file.write_text("{ this is not json", encoding="utf-8")

    result = CommandLog(base_dir=tmp_path).verify()

    assert result["valid"] is False, "a corrupt ledger verified as intact"
    assert "unreadable" in result["message"].lower()


def test_appending_to_a_corrupt_ledger_never_rewrites_it(tmp_path):
    """Appending after a failed load would rewrite the file from scratch.

    The chain is tamper evidence: if the old entries cannot be read, the safe
    move is to leave the bytes alone and report the damage, not to begin again
    at the genesis hash and present the result as intact. The command itself
    still runs, because a broken audit file must not stop a working install.
    """
    log = CommandLog(base_dir=tmp_path)
    log.log("uptime")
    log.log_file.write_text("{ this is not json", encoding="utf-8")
    before = log.log_file.read_bytes()

    corrupted = CommandLog(base_dir=tmp_path)
    corrupted.log("df -h")

    assert corrupted.log_file.read_bytes() == before, "the damaged chain was rewritten"
    assert corrupted.last_log_error
    assert corrupted.verify()["valid"] is False


def test_clear_is_the_explicit_way_out_of_a_corrupt_ledger(tmp_path):
    """A user who chooses `cm cmdlog --clear` gets a working chain back.

    Without resetting the remembered load error, the rewrite would succeed but
    the next append would still be refused, leaving a ledger that looks new and
    silently records nothing.
    """
    log = CommandLog(base_dir=tmp_path)
    log.log("uptime")
    log.log_file.write_text("{ this is not json", encoding="utf-8")

    damaged = CommandLog(base_dir=tmp_path)
    assert damaged.verify()["valid"] is False
    damaged.clear()

    assert damaged.verify()["valid"] is True
    assert json.loads(damaged.log_file.read_text(encoding="utf-8")) == []

    damaged.log("df -h")
    assert damaged.verify()["valid"] is True
    assert damaged.get_recent()[-1]["command"] == "df -h"


def test_a_rewritten_entry_breaks_the_chain(tmp_path):
    """The check that makes the ledger tamper-evident has to keep working."""
    log = CommandLog(base_dir=tmp_path)
    log.log("uptime")
    log.log("df -h")

    entries = json.loads(log.log_file.read_text(encoding="utf-8"))
    entries[0]["args"] = "rewritten"
    log.log_file.write_text(json.dumps(entries), encoding="utf-8")

    result = CommandLog(base_dir=tmp_path).verify()

    assert result["valid"] is False
    assert result["broken_at"] == 0


def test_concurrent_appends_keep_the_chain_verifiable(tmp_path):
    """Two threads that rewrite the whole list at once lose entries.

    Every command runs through this log, and the scheduler and the CLI can
    write at the same time. A dropped entry is a silent gap in the record.
    """
    log = CommandLog(base_dir=tmp_path, max_entries=1000)

    def writer(worker):
        for index in range(5):
            log.log(f"cmd-{worker}-{index}")

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    result = CommandLog(base_dir=tmp_path).verify()

    assert result["valid"] is True, result
    assert result["total"] == 100


def test_a_second_queue_worker_is_refused(tmp_path):
    """Two workers on one queue dispatch the same job twice."""
    first = SmartTaskQueue(nodes={}, queue_dir=tmp_path / "queue")
    second = SmartTaskQueue(nodes={}, queue_dir=tmp_path / "queue")

    with first._worker_lock():
        with pytest.raises(WorkerAlreadyRunningError):
            with second._worker_lock():
                pass


def test_an_ssh_timeout_is_a_named_failure(monkeypatch):
    """A hung ssh call returns a status, never a traceback or a success."""
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ssh", timeout=30)

    monkeypatch.setattr("cloudmesh.core.ssh_util.subprocess.run", timeout)

    output, status = ssh_util._run(["ssh", "example.invalid"], 30)

    assert status == 1
    assert "timed out" in output.lower()


def test_a_missing_ssh_binary_is_a_named_failure(monkeypatch):
    """A controller without OpenSSH must say so, with a non-zero status."""
    def missing(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "ssh")

    monkeypatch.setattr("cloudmesh.core.ssh_util.subprocess.run", missing)

    output, status = ssh_util._run(["ssh", "example.invalid"], 30)

    assert status == 1
    assert "ssh" in output.lower()


def test_a_corrupt_drain_file_is_reported(tmp_path):
    """A maintenance window lost to a bad byte must not be silent.

    `load` still has to return a usable mapping, because the scheduler calls
    it on every pass; but it must leave the reason behind so a caller can show
    it instead of quietly returning a drained node to rotation.
    """
    registry = DrainRegistry(base_dir=tmp_path)
    registry.path.write_text("{ not json", encoding="utf-8")

    assert registry.load() == {}
    assert registry.last_error, "a corrupt drain file was swallowed silently"
