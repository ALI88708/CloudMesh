import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class SQLiteJobStore:
    def __init__(self, queue_dir):
        self.queue_dir = Path(queue_dir)
        self.database_path = self.queue_dir / "queue.sqlite3"
        try:
            descriptor = os.open(
                self.database_path,
                os.O_CREAT | os.O_EXCL | os.O_RDWR,
                0o600,
            )
        except FileExistsError:
            pass
        else:
            os.close(descriptor)
        if os.name != "nt":
            os.chmod(self.database_path, 0o600)
        self._initialize()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database_path, timeout=30)
        try:
            connection.execute("PRAGMA busy_timeout = 30000")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self):
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS jobs_created_at_idx "
                "ON jobs(created_at DESC)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute("BEGIN IMMEDIATE")
            migrated = connection.execute(
                "SELECT value FROM metadata WHERE key = 'legacy_json_migrated'"
            ).fetchone()
            if migrated is not None:
                return

            legacy_files = sorted(
                path for path in self.queue_dir.glob("*.json")
                if re.fullmatch(r"[a-f0-9]{12}", path.stem)
            )
            for path in legacy_files:
                try:
                    job = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise RuntimeError(
                        f"Could not migrate queued job from {path.name}: {exc}"
                    ) from exc
                if (
                    not isinstance(job, dict)
                    or job.get("id") != path.stem
                    or not isinstance(job.get("created_at"), str)
                    or not isinstance(job.get("priority", 0), int)
                    or not isinstance(job.get("status"), str)
                ):
                    raise RuntimeError(
                        f"Could not migrate queued job from {path.name}: "
                        "invalid job record"
                    )
                payload = json.dumps(job, separators=(",", ":"))
                connection.execute(
                    """
                    INSERT OR IGNORE INTO jobs (id, created_at, priority, status, payload)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        job["id"],
                        job["created_at"],
                        job.get("priority", 0),
                        job["status"],
                        payload,
                    ),
                )
            connection.execute(
                "INSERT INTO metadata (key, value) VALUES ('legacy_json_migrated', '1')"
            )

    def save(self, job):
        payload = json.dumps(job, separators=(",", ":"))
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO jobs (id, created_at, priority, status, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    created_at = excluded.created_at,
                    priority = excluded.priority,
                    status = excluded.status,
                    payload = excluded.payload
                """,
                (
                    job["id"],
                    job["created_at"],
                    job.get("priority", 0),
                    job["status"],
                    payload,
                ),
            )

    def get(self, job_id):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not read queued job {job_id}: {exc}") from exc

    def list(self):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM jobs ORDER BY created_at DESC, id"
            ).fetchall()
        try:
            return [json.loads(row[0]) for row in rows]
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not read queued jobs: {exc}") from exc
