import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.queue_storage import SQLiteJobStore
from core.task_queue import SmartTaskQueue


def _job(job_id="0123456789ab", command="echo hello"):
    return {
        "id": job_id,
        "command": command,
        "status": "queued",
        "created_at": "2026-10-01T10:00:00",
        "priority": 3,
        "attempts": [],
    }


def test_legacy_json_jobs_are_migrated_and_remain_reopenable(tmp_path):
    legacy_job = _job()
    legacy_path = tmp_path / f"{legacy_job['id']}.json"
    legacy_path.write_text(json.dumps(legacy_job), encoding="utf-8")

    first = SmartTaskQueue({}, queue_dir=tmp_path)
    migrated = first.get_job(legacy_job["id"], refresh=False)
    assert migrated == legacy_job

    updated = dict(migrated, command="echo updated")
    first._save_job(updated)
    second = SmartTaskQueue({}, queue_dir=tmp_path)

    assert second.get_job(legacy_job["id"], refresh=False)["command"] == "echo updated"
    assert json.loads(legacy_path.read_text(encoding="utf-8")) == legacy_job


def test_malformed_legacy_job_fails_migration_explicitly(tmp_path):
    (tmp_path / "0123456789ab.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Could not migrate queued job"):
        SmartTaskQueue({}, queue_dir=tmp_path)


def test_legacy_job_with_invalid_shape_fails_migration(tmp_path):
    (tmp_path / "0123456789ab.json").write_text(
        json.dumps({"id": "0123456789ab", "status": "queued"}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="invalid job record"):
        SmartTaskQueue({}, queue_dir=tmp_path)


def test_sqlite_store_handles_concurrent_submissions(tmp_path):
    queues = [SmartTaskQueue({}, queue_dir=tmp_path) for _ in range(4)]
    errors = []

    def submit_jobs(queue, offset):
        try:
            for index in range(10):
                queue.submit(f"job-{offset + index}")
        except Exception as exc:
            errors.append(exc)

    workers = [
        threading.Thread(target=submit_jobs, args=(queue, index * 10))
        for index, queue in enumerate(queues)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)

    assert all(not worker.is_alive() for worker in workers)
    assert errors == []
    assert len(queues[0].list_jobs()) == 40


def test_concurrent_initialization_migrates_legacy_jobs_once(tmp_path):
    expected = [_job(f"{index:012x}") for index in range(10)]
    for job in expected:
        (tmp_path / f"{job['id']}.json").write_text(
            json.dumps(job), encoding="utf-8"
        )
    start = threading.Barrier(4)

    def open_queue():
        start.wait(timeout=5)
        return SmartTaskQueue({}, queue_dir=tmp_path)

    with ThreadPoolExecutor(max_workers=4) as executor:
        queues = list(executor.map(lambda _index: open_queue(), range(4)))

    assert all(len(queue.list_jobs()) == len(expected) for queue in queues)


def test_sqlite_store_persists_jobs_and_uses_rollback_journal(tmp_path):
    store = SQLiteJobStore(tmp_path)
    job = _job()
    store.save(job)

    assert store.get(job["id"]) == job
    assert store.list() == [job]
    assert store.database_path.exists()
    with store._connection() as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    assert journal_mode.lower() == "delete"
    assert integrity == "ok"
    if os.name != "nt":
        assert store.database_path.stat().st_mode & 0o777 == 0o600
