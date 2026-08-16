import json
import time
import uuid
import subprocess
import os
import signal
from pathlib import Path
from datetime import datetime


class JobManager:
    """Manage async background jobs on the controller side."""

    def __init__(self, jobs_dir=None):
        self.jobs_dir = Path(jobs_dir or Path(__file__).parent.parent / ".jobs")
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _job_file(self, job_id):
        return self.jobs_dir / f"{job_id}.json"

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
