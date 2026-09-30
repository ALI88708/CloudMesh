import json
import math
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from .node_client import NodeClient


class SmartTaskQueue:
    """Submit async jobs to the node with the most available CPU and memory."""

    def __init__(self, nodes, queue_dir=None, client_factory=NodeClient):
        self.nodes = nodes
        self.queue_dir = Path(queue_dir or Path(__file__).parent.parent / ".task_queue")
        self.client_factory = client_factory
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def _job_file(self, job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9]{12}", job_id):
            return None
        return self.queue_dir / f"{job_id}.json"

    def _save_job(self, job):
        path = self._job_file(job["id"])
        if path is None:
            raise ValueError("Invalid queued job ID")
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
        os.replace(temp_path, path)
        if os.name != "nt":
            os.chmod(path, 0o600)

    def _read_job(self, job_id):
        path = self._job_file(job_id)
        if path is None or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not read queued job {job_id}: {exc}") from exc

    @staticmethod
    def _percentage(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value):
            return None
        return min(100.0, max(0.0, value))

    @classmethod
    def _resource_score(cls, metrics):
        cpu_free = None
        cpu = cls._percentage(metrics.get("cpu_percent"))
        if cpu is not None:
            cpu_free = 100.0 - cpu

        ram = metrics.get("ram")
        if not isinstance(ram, dict):
            ram = {}
        ram_used = cls._percentage(ram.get("percent"))
        if ram_used is None:
            total = ram.get("total_gb")
            free = ram.get("free_gb")
            try:
                total = float(total)
                free = float(free)
                if math.isfinite(total) and math.isfinite(free) and total > 0:
                    ram_used = cls._percentage((total - free) / total * 100)
            except (TypeError, ValueError):
                pass
        ram_free = 100.0 - ram_used if ram_used is not None else None

        available = [value for value in (cpu_free, ram_free) if value is not None]
        if not available:
            return None
        if cpu_free is None:
            return ram_free
        if ram_free is None:
            return cpu_free
        return cpu_free * 0.6 + ram_free * 0.4

    def _client(self, node):
        info = self.nodes[node]
        return self.client_factory(info["host"], info.get("port", 9999), info.get("key"))

    def _rank_nodes(self):
        ranked = []
        errors = []
        for name in sorted(self.nodes):
            try:
                client = self._client(name)
                metrics = client.get_metrics()
            except Exception as exc:
                errors.append({"node": name, "error": str(exc)})
                continue
            score = self._resource_score(metrics) if isinstance(metrics, dict) else None
            if score is None:
                errors.append({"node": name, "error": "Resource metrics unavailable"})
                continue
            ranked.append((score, name, client))
        ranked.sort(key=lambda entry: (-entry[0], entry[1]))
        return ranked, errors

    def submit(self, command, timeout=300):
        if not isinstance(command, str) or not command.strip():
            raise ValueError("A non-empty command is required")
        if not isinstance(timeout, int) or timeout <= 0:
            raise ValueError("Timeout must be a positive integer")

        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "command": command,
            "status": "dispatching",
            "node": None,
            "node_job_id": None,
            "timeout": timeout,
            "created_at": datetime.now().isoformat(),
            "attempts": [],
        }
        self._save_job(job)

        ranked, errors = self._rank_nodes()
        if not ranked:
            job["status"] = "failed"
            details = "; ".join(
                f"{item['node']}: {item['error']}" for item in errors
            )
            job["error"] = "No configured node returned usable resource metrics"
            if details:
                job["error"] += f" ({details})"
            job["attempts"] = errors
            self._save_job(job)
            return job

        for _, name, client in ranked:
            job["node"] = name
            job["status"] = "dispatching"
            job["dispatch_started_at"] = datetime.now().isoformat()
            self._save_job(job)
            try:
                result = client.start_job(command, timeout=timeout)
            except Exception as exc:
                job["status"] = "unknown"
                job["error"] = (
                    f"Could not confirm whether the node accepted the job: {exc}. "
                    "It was not retried to avoid duplicate execution."
                )
                job["attempts"].append({"node": name, "error": str(exc)})
                self._save_job(job)
                return job

            if isinstance(result, dict) and result.get("job_id"):
                job["status"] = result.get("status", "running")
                job["node_job_id"] = result["job_id"]
                job["attempts"].append({"node": name, "status": "accepted"})
                self._save_job(job)
                return job

            if (isinstance(result, dict) and result.get("type") == "error"
                    and result.get("request_sent") is False):
                error = result.get("message", "Connection failed before sending the job")
                job["attempts"].append({
                    "node": name,
                    "status": "not_sent",
                    "error": error,
                })
                job["error"] = error
                self._save_job(job)
                continue

            error = "Node rejected the job"
            if isinstance(result, dict):
                error = result.get("stderr") or result.get("message") or error
            job["node"] = name
            job["error"] = str(error)
            job["attempts"].append({"node": name, "status": "rejected", "error": str(error)})
            if isinstance(result, dict) and result.get("type") == "error" \
                    and result.get("request_sent") is True:
                job["status"] = "unknown"
                job["error"] = (
                    f"{error}. The request may have reached the node; "
                    "it was not retried to avoid duplicate execution."
                )
            else:
                job["status"] = "failed"
            self._save_job(job)
            return job

        job["node"] = None
        job["status"] = "failed"
        details = "; ".join(
            f"{item['node']}: {item['error']}" for item in job["attempts"]
        )
        job["error"] = "Could not send the job to any node with available metrics"
        if details:
            job["error"] += f" ({details})"
        self._save_job(job)
        return job

    def get_job(self, job_id, refresh=True):
        job = self._read_job(job_id)
        if job is None or not refresh:
            return job
        if job.get("status") == "dispatching":
            started_at = job.get("dispatch_started_at") or job.get("created_at")
            try:
                dispatch_age = datetime.now() - datetime.fromisoformat(started_at)
            except (TypeError, ValueError):
                dispatch_age = timedelta(0)
            if dispatch_age > timedelta(seconds=60):
                if job.get("node"):
                    job["status"] = "unknown"
                    job["error"] = (
                        "The controller stopped while dispatching; the node may have "
                        "received the job. It was not replayed."
                    )
                else:
                    job["status"] = "failed"
                    job["error"] = "The controller stopped before selecting a node"
                self._save_job(job)
            return job
        if job.get("status") != "running":
            return job
        node = job.get("node")
        if node not in self.nodes or not job.get("node_job_id"):
            job["last_error"] = "The assigned node is no longer configured"
            self._save_job(job)
            return job
        try:
            result = self._client(node).check_job(job["node_job_id"])
        except Exception as exc:
            job["last_error"] = str(exc)
            self._save_job(job)
            return job
        if not isinstance(result, dict) or not result.get("status"):
            if isinstance(result, dict):
                job["last_error"] = (
                    result.get("error")
                    or result.get("message")
                    or "Could not read remote job status"
                )
            else:
                job["last_error"] = "Invalid remote job status response"
            self._save_job(job)
            return job

        for field in ("status", "finished_at", "exit_code", "stdout", "stderr"):
            if field in result:
                job[field] = result[field]
        job.pop("last_error", None)
        self._save_job(job)
        return job

    def list_jobs(self, refresh=False):
        jobs = []
        for path in self.queue_dir.glob("*.json"):
            job = self._read_job(path.stem)
            if job is not None:
                jobs.append(self.get_job(job["id"]) if refresh else job)
        return sorted(jobs, key=lambda item: item.get("created_at", ""), reverse=True)

    def cancel(self, job_id):
        job = self.get_job(job_id, refresh=False)
        if job is None:
            return None
        if job.get("status") != "running" or not job.get("node_job_id"):
            return {"success": False, "job": job, "error": f"Job status: {job.get('status')}"}
        if job.get("node") not in self.nodes:
            return {"success": False, "job": job, "error": "The assigned node is no longer configured"}
        try:
            result = self._client(job["node"]).kill_job(job["node_job_id"])
        except Exception as exc:
            return {"success": False, "job": job, "error": str(exc)}
        if not isinstance(result, dict) or not result.get("success"):
            if isinstance(result, dict):
                error = result.get("message") or result.get("error") or "Node rejected cancellation"
            else:
                error = "Invalid node response"
            return {"success": False, "job": job, "error": error}
        job["status"] = "cancelled"
        job["finished_at"] = datetime.now().isoformat()
        job.pop("last_error", None)
        self._save_job(job)
        return {"success": True, "job": job}
