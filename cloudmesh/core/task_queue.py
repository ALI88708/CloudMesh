import errno
import json
import math
import os
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from .node_client import NodeClient, save_private_json


class WorkerAlreadyRunningError(RuntimeError):
    """Raised when another worker already coordinates this queue."""


class SmartTaskQueue:
    """Persist, prioritize, and dispatch jobs according to node resources."""

    def __init__(
        self, nodes, queue_dir=None, client_factory=NodeClient,
        failover_grace_seconds=30,
    ):
        self.nodes = nodes
        default_dir = os.environ.get("CLOUDMESH_QUEUE_DIR")
        self.queue_dir = Path(
            queue_dir or default_dir or Path(__file__).parent.parent / ".task_queue"
        ).expanduser()
        self.client_factory = client_factory
        self.failover_grace_seconds = self._finite_nonnegative(
            failover_grace_seconds, "Failover grace period"
        )
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def _job_file(self, job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9]{12}", job_id):
            return None
        return self.queue_dir / f"{job_id}.json"

    def _save_job(self, job):
        path = self._job_file(job["id"])
        if path is None:
            raise ValueError("Invalid queued job ID")
        save_private_json(path, job)

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
    def _node_resources(cls, metrics):
        cpu_free = None
        cpu = cls._percentage(metrics.get("cpu_percent"))
        if cpu is not None:
            cpu_free = 100.0 - cpu

        ram = metrics.get("ram")
        if not isinstance(ram, dict):
            ram = {}
        ram_free_gb = None
        try:
            free = float(ram.get("free_gb"))
            if math.isfinite(free) and free >= 0:
                ram_free_gb = free
        except (TypeError, ValueError):
            pass
        ram_used = cls._percentage(ram.get("percent"))
        if ram_used is None:
            total = ram.get("total_gb")
            try:
                total = float(total)
                free_percent = float(ram.get("free_percent"))
                if math.isfinite(total) and math.isfinite(free_percent) and total > 0:
                    ram_used = cls._percentage(100.0 - free_percent)
            except (TypeError, ValueError):
                pass
        ram_free = 100.0 - ram_used if ram_used is not None else None

        disk = metrics.get("disk")
        if not isinstance(disk, dict):
            disk = {}
        disk_free_gb = None
        try:
            free_disk = float(disk.get("free_gb"))
            if math.isfinite(free_disk) and free_disk >= 0:
                disk_free_gb = free_disk
        except (TypeError, ValueError):
            pass
        disk_used = cls._percentage(disk.get("percent"))
        disk_free = 100.0 - disk_used if disk_used is not None else None

        dimensions = (
            (cpu_free, 0.4),
            (ram_free, 0.45),
            (disk_free, 0.15),
        )
        available = [(value, weight) for value, weight in dimensions if value is not None]
        if not available:
            score = None
        else:
            total_weight = sum(weight for _, weight in available)
            score = sum(value * weight for value, weight in available) / total_weight
        return {
            "cpu_free_percent": cpu_free,
            "ram_free_gb": ram_free_gb,
            "ram_free_percent": ram_free,
            "disk_free_gb": disk_free_gb,
            "disk_free_percent": disk_free,
            "score": score,
        }

    @staticmethod
    def _finite_nonnegative(value, name, maximum=None):
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a non-negative number") from None
        if not math.isfinite(number) or number < 0 or (
                maximum is not None and number > maximum):
            suffix = f" between 0 and {maximum}" if maximum is not None else ""
            raise ValueError(f"{name} must be a non-negative number{suffix}")
        return number

    def _client(self, node):
        info = self.nodes[node]
        if self.client_factory is NodeClient:
            return NodeClient.from_config(info)
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
            resources = self._node_resources(metrics) if isinstance(metrics, dict) else None
            if resources is None or resources["score"] is None:
                errors.append({"node": name, "error": "Resource metrics unavailable"})
                continue
            ranked.append((resources["score"], name, client, resources))
        ranked.sort(key=lambda entry: (-entry[0], entry[1]))
        return ranked, errors

    def submit(self, command, timeout=300, priority=0,
               min_cpu_free_percent=0, min_ram_free_gb=0,
               min_disk_free_gb=0, idempotent=False,
               cpu_claim_percent=None, ram_claim_gb=None,
               disk_claim_gb=None):
        if not isinstance(command, str) or not command.strip():
            raise ValueError("A non-empty command is required")
        if not isinstance(timeout, int) or timeout <= 0:
            raise ValueError("Timeout must be a positive integer")
        if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 9:
            raise ValueError("Priority must be an integer between 0 and 9")
        if not isinstance(idempotent, bool):
            raise ValueError("Idempotent must be a boolean")
        min_cpu_free_percent = self._finite_nonnegative(
            min_cpu_free_percent, "Minimum free CPU", maximum=100
        )
        min_ram_free_gb = self._finite_nonnegative(
            min_ram_free_gb, "Minimum free RAM"
        )
        min_disk_free_gb = self._finite_nonnegative(
            min_disk_free_gb, "Minimum free disk"
        )
        if cpu_claim_percent is not None:
            cpu_claim_percent = self._finite_nonnegative(
                cpu_claim_percent, "CPU claim", maximum=100
            )
        if ram_claim_gb is not None:
            ram_claim_gb = self._finite_nonnegative(ram_claim_gb, "RAM claim")
        if disk_claim_gb is not None:
            disk_claim_gb = self._finite_nonnegative(disk_claim_gb, "Disk claim")

        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "command": command,
            "status": "queued",
            "node": None,
            "node_job_id": None,
            "timeout": timeout,
            "priority": priority,
            "idempotent": idempotent,
            "retry_count": 0,
            "requirements": {
                "min_cpu_free_percent": min_cpu_free_percent,
                "min_ram_free_gb": min_ram_free_gb,
                "min_disk_free_gb": min_disk_free_gb,
                "cpu_claim_percent": cpu_claim_percent,
                "ram_claim_gb": ram_claim_gb,
                "disk_claim_gb": disk_claim_gb,
            },
            "created_at": datetime.now().isoformat(),
            "attempts": [],
        }
        self._save_job(job)
        return job

    @staticmethod
    def _job_order(job):
        return (-job.get("priority", 0), job.get("created_at", ""), job["id"])

    def _refresh_running_jobs(self):
        for job in self.list_jobs():
            if job.get("status") in ("dispatching", "running", "unknown"):
                self.get_job(job["id"])

    @staticmethod
    def _capacity_satisfies(available, minimum, claim):
        if available is None:
            return minimum == 0 and claim == 0
        return available >= minimum and available >= claim

    def _dispatch(self, job, ranked, capacity):
        requirements = job.get("requirements", {})
        min_cpu = requirements.get("min_cpu_free_percent", 0)
        min_ram = requirements.get("min_ram_free_gb", 0)
        min_disk = requirements.get("min_disk_free_gb", 0)
        cpu_claim = requirements.get("cpu_claim_percent")
        ram_claim = requirements.get("ram_claim_gb")
        disk_claim = requirements.get("disk_claim_gb")
        # Missing claims inherit the eligibility thresholds for compatibility
        # with jobs submitted before claims were introduced.
        cpu_claim = min_cpu if cpu_claim is None else cpu_claim
        ram_claim = min_ram if ram_claim is None else ram_claim
        disk_claim = min_disk if disk_claim is None else disk_claim
        candidates = [
            entry for entry in ranked
            if self._capacity_satisfies(
                capacity[entry[1]]["cpu_free_percent"], min_cpu, cpu_claim
            )
            and self._capacity_satisfies(
                capacity[entry[1]]["ram_free_gb"], min_ram, ram_claim
            )
            and self._capacity_satisfies(
                capacity[entry[1]]["disk_free_gb"], min_disk, disk_claim
            )
        ]
        previous_node = job.get("last_node")
        alternative_nodes = [
            entry for entry in candidates if entry[1] != previous_node
        ]
        if previous_node and alternative_nodes:
            candidates = alternative_nodes
        if not candidates:
            job["last_error"] = (
                "Waiting for a node to meet the requested free CPU, RAM, and disk"
            )
            self._save_job(job)
            return False

        for _, name, client, _ in candidates:
            job["node"] = name
            job["status"] = "dispatching"
            job["dispatch_started_at"] = datetime.now().isoformat()
            self._save_job(job)
            try:
                result = client.start_job(job["command"], timeout=job["timeout"])
            except Exception as exc:
                job["status"] = "unknown"
                job["error"] = (
                    f"Could not confirm whether the node accepted the job: {exc}. "
                    "It was not retried to avoid duplicate execution."
                )
                job["attempts"].append({"node": name, "status": "unknown", "error": str(exc)})
                self._save_job(job)
                return False

            if isinstance(result, dict) and result.get("job_id"):
                job["status"] = result.get("status", "running")
                job["node_job_id"] = result["job_id"]
                job["attempts"].append({"node": name, "status": "accepted"})
                if capacity[name]["cpu_free_percent"] is not None:
                    capacity[name]["cpu_free_percent"] = max(
                        0, capacity[name]["cpu_free_percent"] - cpu_claim
                    )
                if capacity[name]["ram_free_gb"] is not None:
                    capacity[name]["ram_free_gb"] = max(
                        0, capacity[name]["ram_free_gb"] - ram_claim
                    )
                if capacity[name]["disk_free_gb"] is not None:
                    capacity[name]["disk_free_gb"] = max(
                        0, capacity[name]["disk_free_gb"] - disk_claim
                    )
                job.pop("last_error", None)
                job.pop("error", None)
                job.pop("last_node", None)
                self._save_job(job)
                return True

            if (isinstance(result, dict) and result.get("type") == "error"
                    and result.get("request_sent") is False):
                error = result.get("message", "Connection failed before sending the job")
                job["attempts"].append({
                    "node": name, "status": "not_sent", "error": error,
                })
                continue

            error = "Node rejected the job"
            if isinstance(result, dict):
                error = result.get("stderr") or result.get("message") or error
            job["error"] = str(error)
            job["attempts"].append({
                "node": name, "status": "rejected", "error": str(error),
            })
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
            return False

        job["status"] = "queued"
        job["node"] = None
        job["last_error"] = "No eligible node accepted the job; it will be retried"
        self._save_job(job)
        return False

    def process_once(self):
        """Refresh active jobs and dispatch queued jobs in priority order."""
        self._refresh_running_jobs()
        pending = sorted(
            (job for job in self.list_jobs() if job.get("status") == "queued"),
            key=self._job_order,
        )
        if not pending:
            return {"dispatched": [], "queued": 0, "running": 0}

        ranked, errors = self._rank_nodes()
        if not ranked:
            message = "No node returned usable resource metrics"
            if errors:
                message += ": " + "; ".join(
                    f"{item['node']}: {item['error']}" for item in errors
                )
            for job in pending:
                job["last_error"] = message
                self._save_job(job)
            return {"dispatched": [], "queued": len(pending), "running": 0}

        capacity = {
            name: dict(resources)
            for _, name, _, resources in ranked
        }
        dispatched = []
        for job in pending:
            if self._dispatch(job, ranked, capacity):
                dispatched.append(job["id"])
        jobs = self.list_jobs()
        return {
            "dispatched": dispatched,
            "queued": sum(job.get("status") == "queued" for job in jobs),
            "running": sum(job.get("status") == "running" for job in jobs),
        }

    def run_worker(self, interval=5, once=False, on_pass=None):
        if not isinstance(interval, (int, float)) or not math.isfinite(interval) or interval < 1:
            raise ValueError("Worker interval must be at least one second")
        with self._worker_lock():
            while True:
                summary = self.process_once()
                if on_pass is not None:
                    on_pass(summary)
                if once:
                    return summary
                time.sleep(interval)

    @contextmanager
    def _worker_lock(self):
        lock_path = self.queue_dir / ".worker.lock"
        with lock_path.open("a+b") as lock_file:
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK):
                    raise
                raise WorkerAlreadyRunningError(
                    "Another queue worker already coordinates this queue"
                ) from exc
            try:
                yield
            finally:
                lock_file.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _handle_unreachable_job(self, job, message):
        now = datetime.now()
        unreachable_since = job.get("unreachable_since")
        if not unreachable_since:
            job["unreachable_since"] = now.isoformat()
            job["last_error"] = message
            self._save_job(job)
            return

        try:
            outage = now - datetime.fromisoformat(unreachable_since)
        except (TypeError, ValueError):
            outage = timedelta(0)
        if outage < timedelta(seconds=self.failover_grace_seconds):
            job["last_error"] = message
            self._save_job(job)
            return
        if job.get("outage_handled"):
            job["last_error"] = message
            self._save_job(job)
            return

        will_retry = job.get("idempotent") and job.get("retry_count", 0) < 1
        attempt = {
            "node": job.get("node"),
            "status": "retry_scheduled" if will_retry else "unknown",
            "error": message,
        }
        job.setdefault("attempts", []).append(attempt)
        if will_retry:
            job["retry_count"] = job.get("retry_count", 0) + 1
            job["last_node"] = job.get("node")
            job["node"] = None
            job["node_job_id"] = None
            job["status"] = "queued"
            job.pop("unreachable_since", None)
            job.pop("error", None)
            job.pop("outage_handled", None)
            job["last_error"] = (
                f"{message}. The idempotent job was queued for one automatic retry."
            )
        else:
            job["status"] = "unknown"
            job["outage_handled"] = True
            job["error"] = (
                f"{message}. The remote job may have run; it was not replayed."
            )
        self._save_job(job)

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
        if job.get("status") not in ("running", "unknown"):
            return job
        node = job.get("node")
        if node not in self.nodes:
            job["last_error"] = "The assigned node is no longer configured"
            self._save_job(job)
            return job
        if not job.get("node_job_id"):
            if job.get("status") != "unknown":
                job["last_error"] = "The assigned node job ID is unavailable"
                self._save_job(job)
            return job
        try:
            result = self._client(node).check_job(job["node_job_id"])
        except Exception as exc:
            job["last_error"] = str(exc)
            self._save_job(job)
            return job
        if (
            isinstance(result, dict)
            and result.get("type") == "error"
            and result.get("request_sent") is False
        ):
            self._handle_unreachable_job(
                job, result.get("message", "The assigned node is unreachable")
            )
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
        job.pop("error", None)
        job.pop("unreachable_since", None)
        job.pop("outage_handled", None)
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
        if job.get("status") == "queued":
            job["status"] = "cancelled"
            job["finished_at"] = datetime.now().isoformat()
            self._save_job(job)
            return {"success": True, "job": job}
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
