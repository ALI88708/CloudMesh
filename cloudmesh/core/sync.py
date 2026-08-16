import os
import hashlib
import shlex
from pathlib import Path


class DirectorySync:
    def __init__(self, server_manager):
        self.server_mgr = server_manager

    def _md5(self, filepath):
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _remote_md5(self, server_name, remote_path):
        safe_path = shlex.quote(remote_path)
        result = self.server_mgr.execute(server_name, f"md5sum {safe_path} 2>/dev/null || echo none")
        if result["exit_code"] != 0 or "none" in result["stdout"]:
            return None
        return result["stdout"].split()[0]

    def _remote_exists(self, server_name, remote_path):
        safe_path = shlex.quote(remote_path)
        result = self.server_mgr.execute(server_name, f"test -e {safe_path} && echo yes || echo no")
        return "yes" in result["stdout"]

    def _remote_is_dir(self, server_name, remote_path):
        safe_path = shlex.quote(remote_path)
        result = self.server_mgr.execute(server_name, f"test -d {safe_path} && echo yes || echo no")
        return "yes" in result["stdout"]

    def sync_to(self, local_dir, server_name, remote_dir):
        results = []
        local_path = Path(local_dir)

        if not local_path.exists():
            return [{"success": False, "error": f"Local path not found: {local_dir}"}]

        safe_remote = shlex.quote(remote_dir)
        self.server_mgr.execute(server_name, f"mkdir -p {safe_remote}")

        if local_path.is_file():
            remote_file = f"{remote_dir}/{local_path.name}"
            r = self._sync_file(str(local_path), server_name, remote_file)
            results.append(r)
            return results

        for root, dirs, files in os.walk(local_path):
            for f in files:
                local_file = os.path.join(root, f)
                rel_path = os.path.relpath(local_file, local_path)
                remote_file = f"{remote_dir}/{rel_path}".replace("\\", "/")

                remote_dir_part = os.path.dirname(remote_file)
                safe_dir = shlex.quote(remote_dir_part)
                self.server_mgr.execute(server_name, f"mkdir -p {safe_dir}")

                r = self._sync_file(local_file, server_name, remote_file)
                r["file"] = rel_path
                results.append(r)

        return results

    def _sync_file(self, local_file, server_name, remote_file):
        local_md5 = self._md5(local_file)
        remote_md5 = self._remote_md5(server_name, remote_file)

        if local_md5 == remote_md5:
            return {"success": True, "action": "skipped", "message": "Already up to date"}

        try:
            from .transfer import FileTransfer
            transfer = FileTransfer(self.server_mgr)
            transfer.upload(server_name, local_file, remote_file)
            return {"success": True, "action": "synced", "message": f"Synced to {remote_file}"}
        except Exception as e:
            return {"success": False, "action": "error", "message": str(e)}

    def sync_from(self, server_name, remote_dir, local_dir):
        results = []
        local_path = Path(local_dir)
        local_path.mkdir(parents=True, exist_ok=True)

        safe_remote = shlex.quote(remote_dir)
        result = self.server_mgr.execute(server_name, f"find {safe_remote} -type f 2>/dev/null")
        if result["exit_code"] != 0:
            return [{"success": False, "error": "Could not list remote files"}]

        remote_files = result["stdout"].strip().split("\n")
        for remote_file in remote_files:
            if not remote_file.strip():
                continue
            rel_path = os.path.relpath(remote_file, remote_dir)
            local_file = local_path / rel_path
            local_file.parent.mkdir(parents=True, exist_ok=True)

            local_md5 = self._md5(str(local_file)) if local_file.exists() else None
            remote_md5 = self._remote_md5(server_name, remote_file)

            if local_md5 == remote_md5:
                results.append({"success": True, "action": "skipped", "file": rel_path})
                continue

            try:
                from .transfer import FileTransfer
                transfer = FileTransfer(self.server_mgr)
                transfer.download(server_name, remote_file, str(local_file))
                results.append({"success": True, "action": "synced", "file": rel_path})
            except Exception as e:
                results.append({"success": False, "action": "error", "file": rel_path, "message": str(e)})

        return results

    def sync_between(self, from_server, to_server, remote_from, remote_to):
        import tempfile
        import shutil
        tmp_dir = tempfile.mkdtemp(prefix="cloudmesh_sync_")
        try:
            self.sync_from(from_server, remote_from, tmp_dir)
            return self.sync_to(tmp_dir, to_server, remote_to)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
