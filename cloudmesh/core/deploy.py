import tempfile
import os


class PackageDeployer:
    def __init__(self, server_manager):
        self.server_mgr = server_manager
        self._detect_cmds = {
            "apt": "apt list --installed 2>/dev/null | grep -q '{pkg}' && echo installed || echo not_installed",
            "yum": "rpm -q {pkg} >/dev/null 2>&1 && echo installed || echo not_installed",
            "brew": "brew list {pkg} >/dev/null 2>&1 && echo installed || echo not_installed",
            "choco": "choco list --local-only {pkg} >/dev/null 2>&1 && echo installed || echo not_installed",
            "winget": "winget list --name {pkg} >/dev/null 2>&1 && echo installed || echo not_installed",
        }
        self._install_cmds = {
            "apt": "sudo apt update && sudo apt install -y {pkg}",
            "yum": "sudo yum install -y {pkg}",
            "brew": "brew install {pkg}",
            "choco": "choco install {pkg} -y",
            "winget": "winget install --name {pkg} --accept-source-agreements",
        }

    def _detect_package_manager(self, server_name):
        info = self.server_mgr.get_server_info(server_name)
        os_type = info.get("os_type", "linux")

        if os_type == "windows":
            result = self.server_mgr.execute(server_name, "where choco >nul 2>&1 && echo choco || where winget >nul 2>&1 && echo winget || echo none")
            if "choco" in result.get("stdout", ""):
                return "choco"
            elif "winget" in result.get("stdout", ""):
                return "winget"
            return None

        for mgr in ["apt", "yum", "brew"]:
            result = self.server_mgr.execute(server_name, f"which {mgr} >/dev/null 2>&1 && echo {mgr} || echo none")
            if mgr in result.get("stdout", ""):
                return mgr
        return None

    def check_installed(self, server_name, package):
        mgr = self._detect_package_manager(server_name)
        if mgr is None:
            return None
        cmd = self._detect_cmds.get(mgr, "").format(pkg=package)
        result = self.server_mgr.execute(server_name, cmd)
        return "installed" in result.get("stdout", "")

    def install(self, server_name, package):
        mgr = self._detect_package_manager(server_name)
        if mgr is None:
            return {"success": False, "error": "No package manager found"}
        cmd = self._install_cmds.get(mgr, "").format(pkg=package)
        result = self.server_mgr.execute(server_name, cmd)
        return {
            "success": result["exit_code"] == 0,
            "output": result["stdout"],
            "error": result["stderr"] if result["exit_code"] != 0 else None,
        }

    def install_on_all(self, package):
        results = {}
        for name in self.server_mgr.list_servers():
            try:
                installed = self.check_installed(name, package)
                if installed:
                    results[name] = {"success": True, "message": "Already installed"}
                else:
                    result = self.install(name, package)
                    results[name] = result
            except Exception as e:
                results[name] = {"success": False, "error": str(e)}
        return results

    def install_python(self, server_names=None):
        if server_names is None:
            server_names = self.server_mgr.list_servers()

        results = {}
        for name in server_names:
            try:
                info = self.server_mgr.get_server_info(name)
                os_type = info.get("os_type", "linux")

                if os_type == "windows":
                    result = self.install(name, "python")
                else:
                    result = self.install(name, "python3")

                results[name] = result
            except Exception as e:
                results[name] = {"success": False, "error": str(e)}
        return results

    def install_nodejs(self, server_names=None):
        if server_names is None:
            server_names = self.server_mgr.list_servers()

        results = {}
        for name in server_names:
            try:
                info = self.server_mgr.get_server_info(name)
                os_type = info.get("os_type", "linux")

                if os_type == "windows":
                    result = self.install(name, "nodejs-lts")
                else:
                    result = self.install(name, "nodejs")

                results[name] = result
            except Exception as e:
                results[name] = {"success": False, "error": str(e)}
        return results

    def run_script(self, server_name, script_content, script_name="cloudmesh_script.sh"):
        info = self.server_mgr.get_server_info(server_name)
        os_type = info.get("os_type", "linux")

        local_tmp = os.path.join(tempfile.gettempdir(), script_name)
        with open(local_tmp, "w") as f:
            f.write(script_content)

        try:
            from .transfer import FileTransfer
            transfer = FileTransfer(self.server_mgr)

            if os_type == "windows":
                remote_path = f"C:\\temp\\{script_name}"
                self.server_mgr.execute(server_name, "mkdir C:\\temp 2>nul")
                transfer.upload(server_name, local_tmp, remote_path)
                result = self.server_mgr.execute(server_name, remote_path)
            else:
                remote_path = f"/tmp/{script_name}"
                transfer.upload(server_name, local_tmp, remote_path)
                self.server_mgr.execute(server_name, f"chmod +x {remote_path}")
                result = self.server_mgr.execute(server_name, f"bash {remote_path}")

            return {
                "success": result["exit_code"] == 0,
                "output": result["stdout"],
                "error": result["stderr"] if result["exit_code"] != 0 else None,
            }
        finally:
            if os.path.exists(local_tmp):
                os.remove(local_tmp)
