import json
from pathlib import Path
from datetime import datetime


class CheckpointManager:
    def __init__(self, checkpoint_dir=None):
        self.checkpoint_dir = Path(checkpoint_dir or Path(__file__).parent.parent / ".checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _cp_file(self, job_id):
        return self.checkpoint_dir / f"{job_id}.json"

    def save_checkpoint(self, job_id, command, server, progress, stdout="", stderr="", exit_code=None):
        cp = {
            "job_id": job_id,
            "command": command,
            "server": server,
            "progress": progress,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "checkpointed_at": datetime.now().isoformat(),
        }
        self._cp_file(job_id).write_text(json.dumps(cp, indent=2))
        return True

    def load_checkpoint(self, job_id):
        f = self._cp_file(job_id)
        if f.exists():
            try:
                return json.loads(f.read_text())
            except Exception:
                return None
        return None

    def needs_recovery(self, alive_nodes=None):
        alive_nodes = alive_nodes or set()
        recoverable = []
        for f in self.checkpoint_dir.glob("*.json"):
            try:
                cp = json.loads(f.read_text())
                job_id = cp.get("job_id")
                server = cp.get("server")
                if server and alive_nodes and server not in alive_nodes:
                    recoverable.append(cp)
            except Exception:
                continue
        return recoverable

    def list_checkpoints(self):
        checkpoints = []
        for f in sorted(self.checkpoint_dir.glob("*.json")):
            try:
                cp = json.loads(f.read_text())
                checkpoints.append(cp)
            except Exception:
                continue
        return checkpoints

    def remove_checkpoint(self, job_id):
        f = self._cp_file(job_id)
        if f.exists():
            f.unlink()
            return True
        return False

    def clear_all(self):
        removed = 0
        for f in self.checkpoint_dir.glob("*.json"):
            try:
                f.unlink()
                removed += 1
            except Exception:
                continue
        return removed
