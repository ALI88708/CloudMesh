import json
import re
import time
import uuid
import subprocess
import os
import signal
from pathlib import Path
from datetime import datetime

from .paths import state_file

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class JobManager:
    """Manage async background jobs on the controller side."""

    def __init__(self, jobs_dir=None, checkpoint_dir=None):
        self.jobs_dir = Path(jobs_dir) if jobs_dir else state_file(".jobs")
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        if checkpoint_dir is not None:
            self._checkpoint_dir = Path(checkpoint_dir)
        elif jobs_dir is not None:
            self._checkpoint_dir = self.jobs_dir.parent / ".checkpoints"
        else:
            self._checkpoint_dir = None

    def _job_file(self, job_id):
        if not isinstance(job_id, str) or not _SAFE_ID.fullmatch(job_id):
            raise ValueError(f"Invalid job ID: {job_id!r}")
        return self.jobs_dir / f"{job_id}.json"

    def _checkpoint_manager(self):
        from cloudmesh.core.checkpoint import CheckpointManager
        return CheckpointManager(self._checkpoint_dir)

    def create_job(self, command, server_name, timeout=300):
        job_id = str(uuid.uuid4())[:8]
        job = {
            "id": job_id,
            "command": command,
            "server": server_name,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "timeout": timeout,
            "progress": 0,
            "recoverable": True,
            "last_checkpoint": None,
        }
        self._job_file(job_id).write_text(json.dumps(job, indent=2))
        return job_id

    def update_job(self, job_id, **kwargs):
        f = self._job_file(job_id)
        if not f.exists():
            return False
        job = json.loads(f.read_text())
        job.update(kwargs)
        f.write_text(json.dumps(job, indent=2))
        return True

    def checkpoint_job(self, job_id, stdout="", stderr="", exit_code=None):
        job = self.get_job(job_id)
        if not job:
            return False

        self.update_job(
            job_id,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            last_checkpoint=datetime.now().isoformat(),
        )

        cp = self._checkpoint_manager()
        cp.save_checkpoint(
            job_id=job_id,
            command=job.get("command", ""),
            server=job.get("server", ""),
            progress=job.get("progress", 0),
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
        )
        return True

    def recover_job(self, job_id, new_server=None):
        try:
            cp_import = self._checkpoint_manager()
        except ImportError:
            return None

        cp = cp_import.load_checkpoint(job_id)
        if not cp:
            return None

        new_server = new_server or cp.get("server", "")
        new_id = self.create_job(cp.get("command", ""), new_server)
        self.update_job(
            new_id,
            status="pending",
            progress=cp.get("progress", 0),
            stdout=cp.get("stdout", ""),
            stderr=cp.get("stderr", ""),
        )

        cp_import.remove_checkpoint(job_id)

        return {"old_job_id": job_id, "new_job_id": new_id, "server": new_server}

    def get_recoverable_jobs(self, alive_nodes=None):
        cp = self._checkpoint_manager()
        return cp.needs_recovery(alive_nodes)

    def get_job(self, job_id):
        f = self._job_file(job_id)
        if not f.exists():
            return None
        return json.loads(f.read_text())

    def list_jobs(self, status=None):
        jobs = []
        for f in sorted(self.jobs_dir.glob("*.json")):
            try:
                job = json.loads(f.read_text())
                if status is None or job.get("status") == status:
                    jobs.append(job)
            except Exception:
                continue
        return jobs

    def remove_job(self, job_id):
        f = self._job_file(job_id)
        if f.exists():
            f.unlink()
            return True
        return False

    def cleanup_old(self, max_age_hours=24):
        cutoff = time.time() - (max_age_hours * 3600)
        removed = 0
        for f in self.jobs_dir.glob("*.json"):
            try:
                if f.stat().st_mtime < cutoff:
                    job = json.loads(f.read_text())
                    if job.get("status") in ("completed", "failed", "cancelled"):
                        f.unlink()
                        removed += 1
            except Exception:
                continue
        return removed
