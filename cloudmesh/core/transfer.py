import os
import tempfile
import paramiko
import stat
import shlex


class FileTransfer:
    def __init__(self, server_manager):
        self.server_mgr = server_manager

    def upload(self, server_name, local_path, remote_path):
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")

        client = self.server_mgr.connect(server_name)
        sftp = client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
            return {"success": True, "message": f"Uploaded to {server_name}:{remote_path}"}
        finally:
            sftp.close()

    def download(self, server_name, remote_path, local_path):
        client = self.server_mgr.connect(server_name)
        sftp = client.open_sftp()
        try:
            sftp.get(remote_path, local_path)
            return {"success": True, "message": f"Downloaded from {server_name}:{remote_path}"}
        finally:
            sftp.close()

    def transfer_between(self, from_server, to_server, remote_path_from, remote_path_to=None):
        if remote_path_to is None:
            remote_path_to = os.path.basename(remote_path_from)

        tmp_path = os.path.join(tempfile.gettempdir(), f"cloudmesh_transfer_{os.path.basename(remote_path_from)}")

        self.download(from_server, remote_path_from, tmp_path)
        try:
            result = self.upload(to_server, tmp_path, remote_path_to)
            return result
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def list_remote(self, server_name, remote_path):
        client = self.server_mgr.connect(server_name)
        sftp = client.open_sftp()
        try:
            entries = sftp.listdir_attr(remote_path)
            result = []
            for entry in entries:
                is_dir = stat.S_ISDIR(entry.st_mode)
                result.append({
                    "name": entry.filename,
                    "is_dir": is_dir,
                    "size": entry.st_size,
                    "permissions": oct(entry.st_mode)[-3:],
                })
            return result
        finally:
            sftp.close()

    def upload_directory(self, server_name, local_dir, remote_dir):
        results = []
        for root, dirs, files in os.walk(local_dir):
            for f in files:
                local_file = os.path.join(root, f)
                rel_path = os.path.relpath(local_file, local_dir)
                remote_file = f"{remote_dir}/{rel_path}".replace("\\", "/")
                remote_dir_path = os.path.dirname(remote_file)
                try:
                    client = self.server_mgr.connect(server_name)
                    client.exec_command(f"mkdir -p {shlex.quote(remote_dir_path)}")
                except Exception:
                    pass
                result = self.upload(server_name, local_file, remote_file)
                results.append(result)
        return results
