import re, shlex

from cloudmesh.core.ssh_util import run_ssh
from cloudmesh.core.server_config import get_server as _store_server
from cloudmesh.core.server_config import load_server_config

_IMAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@-]{0,254}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PORT_RE = re.compile(r"^[0-9A-Za-z_.:\[\]/-]+$")


def _load_config():
    return load_server_config()

def _get_server(name):
    return _store_server(name)

def _run_ssh(host, user, key, cmd):
    return run_ssh(host, user, key, cmd)

BSD_OS_TYPES = ("freebsd", "openbsd", "netbsd")

def _bsd_message(os_type):
    return f"Docker is not supported on {os_type} servers; use the platform package manager (pkg) and rc.d units"

def unsupported_on_bsd(server_name):
    """Return the explanation for BSD servers, otherwise None."""
    srv = _get_server(server_name)
    if not srv:
        return None
    os_type = (srv.get("os_type") or "").lower()
    if os_type in BSD_OS_TYPES:
        return _bsd_message(os_type)
    return None

def docker_list(args=None):
    cfg = _load_config()
    targets = []
    if args and hasattr(args, "server") and args.server:
        srv = _get_server(args.server)
        if srv:
            targets = [(args.server, srv)]
    else:
        for name, srv in cfg.get("servers", {}).items():
            targets.append((name, srv))
        for name, srv in cfg.get("nodes", {}).items():
            targets.append((name, srv))

    if not targets:
        return "No servers configured. Add servers with: cm server add"

    results = []
    for name, srv in targets:
        os_type = (srv.get("os_type") or "").lower()
        if os_type in BSD_OS_TYPES:
            results.append({"server": name, "containers": [], "error": _bsd_message(os_type)})
            continue

        host = srv.get("host", "")
        user = srv.get("user", "root")
        key = srv.get("key", "")

        out, rc = _run_ssh(host, user, key, "docker ps --format '{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}' 2>/dev/null")
        if rc != 0:
            results.append({"server": name, "containers": [], "error": "Docker not installed or not running"})
            continue

        containers = []
        for line in out.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 5:
                containers.append({
                    "id": parts[0],
                    "name": parts[1],
                    "image": parts[2],
                    "status": parts[3],
                    "ports": parts[4]
                })
        results.append({"server": name, "containers": containers})

    return results

def docker_action(server_name, action, container=None):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    msg = unsupported_on_bsd(server_name)
    if msg:
        return msg

    host = srv.get("host", "")
    user = srv.get("user", "root")
    key = srv.get("key", "")

    if action == "ps":
        out, rc = _run_ssh(host, user, key, "docker ps -a --format 'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'")
        return out
    elif action == "start" and container:
        out, rc = _run_ssh(host, user, key, f"docker start {shlex.quote(container)}")
        return f"Started: {container}" if rc == 0 else f"Failed: {out}"
    elif action == "stop" and container:
        out, rc = _run_ssh(host, user, key, f"docker stop {shlex.quote(container)}")
        return f"Stopped: {container}" if rc == 0 else f"Failed: {out}"
    elif action == "restart" and container:
        out, rc = _run_ssh(host, user, key, f"docker restart {shlex.quote(container)}")
        return f"Restarted: {container}" if rc == 0 else f"Failed: {out}"
    elif action == "rm" and container:
        out, rc = _run_ssh(host, user, key, f"docker rm -f {shlex.quote(container)}")
        return f"Removed: {container}" if rc == 0 else f"Failed: {out}"
    elif action == "logs" and container:
        out, rc = _run_ssh(
            host, user, key, f"docker logs --tail 50 {shlex.quote(container)} 2>&1"
        )
        return out
    elif action == "exec" and container:
        cmd = getattr(server_name, "cmd", "sh") if hasattr(server_name, "cmd") else "sh"
        out, rc = _run_ssh(
            host, user, key, f"docker exec {shlex.quote(container)} {cmd}"
        )
        return out
    elif action == "images":
        out, rc = _run_ssh(host, user, key, "docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'")
        return out
    elif action == "compose_up":
        out, rc = _run_ssh(host, user, key, "docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null")
        return f"Compose started" if rc == 0 else f"Failed: {out}"
    elif action == "compose_down":
        out, rc = _run_ssh(host, user, key, "docker compose down 2>/dev/null || docker-compose down 2>/dev/null")
        return f"Compose stopped" if rc == 0 else f"Failed: {out}"
    elif action == "prune":
        out, rc = _run_ssh(host, user, key, "docker system prune -f")
        return out
    elif action == "stats":
        out, rc = _run_ssh(host, user, key, "docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}'")
        return out
    else:
        return f"Unknown action: {action}"

def docker_deploy(server_name, image, name=None, ports=None, env=None):
    srv = _get_server(server_name)
    if not srv:
        return f"Server '{server_name}' not found"
    msg = unsupported_on_bsd(server_name)
    if msg:
        return msg

    host = srv.get("host", "")
    user = srv.get("user", "root")
    key = srv.get("key", "")

    if not _IMAGE_RE.fullmatch(image or ""):
        return f"Invalid image reference: {image}"
    if name and not _NAME_RE.fullmatch(name):
        return f"Invalid container name: {name}"
    for port in ports or []:
        if not _PORT_RE.fullmatch(str(port)):
            return f"Invalid port mapping: {port}"
    for key_name in (env or {}):
        if not _ENV_KEY_RE.fullmatch(key_name):
            return f"Invalid environment variable name: {key_name}"

    cmd = "docker run -d --restart unless-stopped"
    if name:
        cmd += f" --name {name}"
    for port in ports or []:
        cmd += f" -p {port}"
    for key_name, value in (env or {}).items():
        cmd += f" -e {shlex.quote(f'{key_name}={value}')}"
    cmd += f" {shlex.quote(image)}"

    out, rc = _run_ssh(host, user, key, cmd)
    return f"Deployed {image}" if rc == 0 else f"Failed: {out}"


class DockerManager:
    """Adapter exposing the CLI-facing Docker API over the functions above."""

    def _bsd_guard(self, server):
        return unsupported_on_bsd(server)

    def list_servers(self):
        """Return the names of all configured servers and nodes."""
        cfg = _load_config()
        names = list(cfg.get("servers", {}).keys()) + list(cfg.get("nodes", {}).keys())
        if not names:
            return "No servers configured. Add servers with: cm server add"
        return names

    def list_containers(self, server):
        """Return a formatted listing of containers running on the given server."""
        msg = self._bsd_guard(server)
        if msg:
            return msg
        results = docker_list()
        if isinstance(results, str):
            return results
        for entry in results:
            if entry.get("server") == server:
                containers = entry.get("containers", [])
                if entry.get("error"):
                    return f"{server}: {entry['error']}"
                if not containers:
                    return f"{server}: no running containers"
                lines = [f"{c['id'][:12]}  {c['name']}  {c['image']}  {c['status']}" for c in containers]
                return "\n".join(lines)
        return f"Server '{server}' not found"

    def docker_compose(self, path, server, action="up"):
        """Run docker compose up or down for the given path on the server."""
        srv = _get_server(server)
        if not srv:
            return f"Server '{server}' not found"
        msg = self._bsd_guard(server)
        if msg:
            return msg
        host, user, key = srv.get("host", ""), srv.get("user", "root"), srv.get("key", "")
        if action == "down":
            return docker_action(server, "compose_down")
        cmd = (
            f"cd {shlex.quote(path)} && docker compose up -d 2>/dev/null "
            "|| docker-compose up -d 2>/dev/null"
        )
        out, rc = _run_ssh(host, user, key, cmd)
        return "Compose started" if rc == 0 else f"Failed: {out}"

    def container_stats(self, server):
        """Return live resource usage stats for containers on the server."""
        msg = self._bsd_guard(server)
        if msg:
            return msg
        return docker_action(server, "stats")

    def list_images(self, server):
        """Return the list of Docker images available on the server."""
        msg = self._bsd_guard(server)
        if msg:
            return msg
        return docker_action(server, "images")

    def pull_image(self, image, server):
        """Pull the given Docker image on the server."""
        srv = _get_server(server)
        if not srv:
            return f"Server '{server}' not found"
        msg = self._bsd_guard(server)
        if msg:
            return msg
        if not _IMAGE_RE.fullmatch(image or ""):
            return f"Invalid image reference: {image}"
        out, rc = _run_ssh(srv.get("host", ""), srv.get("user", "root"), srv.get("key", ""),
                            f"docker pull {shlex.quote(image)}")
        return f"Pulled {image}" if rc == 0 else f"Failed: {out}"

    def exec_command(self, container, cmd, server):
        """Execute a command inside a container on the server."""
        srv = _get_server(server)
        if not srv:
            return f"Server '{server}' not found"
        msg = self._bsd_guard(server)
        if msg:
            return msg
        out, rc = _run_ssh(srv.get("host", ""), srv.get("user", "root"), srv.get("key", ""),
                            f"docker exec {shlex.quote(container)} {cmd}")
        return out if rc == 0 else f"Failed: {out}"

    def container_logs(self, container, server, lines=50):
        """Return the last N lines of logs for a container on the server."""
        srv = _get_server(server)
        if not srv:
            return f"Server '{server}' not found"
        msg = self._bsd_guard(server)
        if msg:
            return msg
        try:
            lines = max(int(lines), 1)
        except (TypeError, ValueError):
            lines = 50
        out, rc = _run_ssh(srv.get("host", ""), srv.get("user", "root"), srv.get("key", ""),
                            f"docker logs --tail {lines} {shlex.quote(container)} 2>&1")
        return out if rc == 0 else f"Failed: {out}"

    def cleanup(self, server):
        """Prune stopped containers and unused images on the server."""
        srv = _get_server(server)
        if not srv:
            return f"Server '{server}' not found"
        msg = self._bsd_guard(server)
        if msg:
            return msg
        out, rc = _run_ssh(srv.get("host", ""), srv.get("user", "root"), srv.get("key", ""),
                            "docker container prune -f && docker image prune -f")
        return out if rc == 0 else f"Failed: {out}"

    def prune(self, server):
        """Run a Docker system prune on the server."""
        msg = self._bsd_guard(server)
        if msg:
            return msg
        return docker_action(server, "prune")
