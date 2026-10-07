import json, os, subprocess, socket

from cloudmesh.core.ssh_util import run_ssh

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def _load_config():
    p = os.path.join(DATA_DIR, "cloudmesh.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}

def _save_config(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    p = os.path.join(DATA_DIR, "cloudmesh.json")
    with open(p, "w") as f:
        json.dump(cfg, f, indent=2)

def _get_server(name):
    cfg = _load_config()
    servers = cfg.get("servers", {})
    if name in servers:
        return servers[name]
    nodes = cfg.get("nodes", {})
    if name in nodes:
        return nodes[name]
    return None

def _run_ssh(host, user, key, cmd):
    return run_ssh(host, user, key, cmd)

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

    host = srv.get("host", "")
    user = srv.get("user", "root")
    key = srv.get("key", "")

    if action == "ps":
        out, rc = _run_ssh(host, user, key, "docker ps -a --format 'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'")
        return out
    elif action == "start" and container:
        out, rc = _run_ssh(host, user, key, f"docker start {container}")
        return f"Started: {container}" if rc == 0 else f"Failed: {out}"
    elif action == "stop" and container:
        out, rc = _run_ssh(host, user, key, f"docker stop {container}")
        return f"Stopped: {container}" if rc == 0 else f"Failed: {out}"
    elif action == "restart" and container:
        out, rc = _run_ssh(host, user, key, f"docker restart {container}")
        return f"Restarted: {container}" if rc == 0 else f"Failed: {out}"
    elif action == "rm" and container:
        out, rc = _run_ssh(host, user, key, f"docker rm -f {container}")
        return f"Removed: {container}" if rc == 0 else f"Failed: {out}"
    elif action == "logs" and container:
        out, rc = _run_ssh(host, user, key, f"docker logs --tail 50 {container} 2>&1")
        return out
    elif action == "exec" and container:
        cmd = getattr(server_name, "cmd", "sh") if hasattr(server_name, "cmd") else "sh"
        out, rc = _run_ssh(host, user, key, f"docker exec {container} {cmd}")
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

    host = srv.get("host", "")
    user = srv.get("user", "root")
    key = srv.get("key", "")

    cmd = f"docker run -d --restart unless-stopped"
    if name:
        cmd += f" --name {name}"
    if ports:
        for p in ports:
            cmd += f" -p {p}"
    if env:
        for k, v in env.items():
            cmd += f" -e {k}={v}"
    cmd += f" {image}"

    out, rc = _run_ssh(host, user, key, cmd)
    return f"Deployed {image}" if rc == 0 else f"Failed: {out}"


class DockerManager:
    """Adapter exposing the CLI-facing Docker API over the functions above."""

    def list_servers(self):
        """Return the names of all configured servers and nodes."""
        cfg = _load_config()
        names = list(cfg.get("servers", {}).keys()) + list(cfg.get("nodes", {}).keys())
        if not names:
            return "No servers configured. Add servers with: cm server add"
        return names

    def list_containers(self, server):
        """Return a formatted listing of containers running on the given server."""
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
        host, user, key = srv.get("host", ""), srv.get("user", "root"), srv.get("key", "")
        if action == "down":
            return docker_action(server, "compose_down")
        cmd = f"cd {path} && docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null"
        out, rc = _run_ssh(host, user, key, cmd)
        return "Compose started" if rc == 0 else f"Failed: {out}"

    def container_stats(self, server):
        """Return live resource usage stats for containers on the server."""
        return docker_action(server, "stats")

    def list_images(self, server):
        """Return the list of Docker images available on the server."""
        return docker_action(server, "images")

    def pull_image(self, image, server):
        """Pull the given Docker image on the server."""
        srv = _get_server(server)
        if not srv:
            return f"Server '{server}' not found"
        out, rc = _run_ssh(srv.get("host", ""), srv.get("user", "root"), srv.get("key", ""),
                            f"docker pull {image}")
        return f"Pulled {image}" if rc == 0 else f"Failed: {out}"

    def exec_command(self, container, cmd, server):
        """Execute a command inside a container on the server."""
        srv = _get_server(server)
        if not srv:
            return f"Server '{server}' not found"
        out, rc = _run_ssh(srv.get("host", ""), srv.get("user", "root"), srv.get("key", ""),
                            f"docker exec {container} {cmd}")
        return out if rc == 0 else f"Failed: {out}"

    def container_logs(self, container, server, lines=50):
        """Return the last N lines of logs for a container on the server."""
        srv = _get_server(server)
        if not srv:
            return f"Server '{server}' not found"
        try:
            lines = max(int(lines), 1)
        except (TypeError, ValueError):
            lines = 50
        out, rc = _run_ssh(srv.get("host", ""), srv.get("user", "root"), srv.get("key", ""),
                            f"docker logs --tail {lines} {container} 2>&1")
        return out if rc == 0 else f"Failed: {out}"

    def cleanup(self, server):
        """Prune stopped containers and unused images on the server."""
        srv = _get_server(server)
        if not srv:
            return f"Server '{server}' not found"
        out, rc = _run_ssh(srv.get("host", ""), srv.get("user", "root"), srv.get("key", ""),
                            "docker container prune -f && docker image prune -f")
        return out if rc == 0 else f"Failed: {out}"

    def prune(self, server):
        """Run a Docker system prune on the server."""
        return docker_action(server, "prune")
