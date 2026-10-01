import subprocess
import warnings


class SSHWarning(UserWarning):
    pass


def _as_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _format_output(stdout, stderr="", diagnostic=None):
    parts = [part.strip() for part in (_as_text(stdout), _as_text(stderr)) if part and part.strip()]
    output = parts[0] if parts else ""
    if len(parts) > 1:
        output = f"{output}\nstderr: {parts[1]}" if output else f"stderr: {parts[1]}"
    if diagnostic:
        output = f"{output}\n{diagnostic}" if output else diagnostic
    return output.strip()


def _run(ssh_cmd, timeout, stdin_data=None):
    try:
        result = subprocess.run(
            ssh_cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = _format_output(
            result.stdout,
            result.stderr if result.returncode != 0 else "",
        )
        if result.returncode != 0 and not _as_text(result.stderr).strip():
            output = _format_output(
                output,
                diagnostic=f"SSH command exited with status {result.returncode}",
            )
        return output, result.returncode
    except subprocess.TimeoutExpired as exc:
        output = _format_output(
            exc.stdout,
            exc.stderr,
            diagnostic=f"SSH command timed out after {timeout} seconds",
        )
        return output, 1
    except Exception as exc:
        return str(exc), 1


def warn_host_key_disabled(host):
    warnings.warn(
        f"StrictHostKeyChecking disabled for {host}. "
        "This connection is vulnerable to MITM attacks. "
        f"Add the host key to ~/.ssh/known_hosts with: ssh-keyscan {host} >> ~/.ssh/known_hosts",
        SSHWarning, stacklevel=3
    )


def build_ssh_cmd(host, user, key, cmd=None, extra_flags=None, strict=True):
    ssh_cmd = ["ssh", "-o", "ConnectTimeout=5"]
    if strict:
        ssh_cmd += ["-o", "StrictHostKeyChecking=yes"]
    else:
        warn_host_key_disabled(host)
        ssh_cmd += ["-o", "StrictHostKeyChecking=no"]
    if key:
        ssh_cmd += ["-i", key]
    if extra_flags:
        ssh_cmd += extra_flags
    ssh_cmd += [f"{user}@{host}"]
    if cmd:
        ssh_cmd.append(cmd)
    return ssh_cmd


def run_ssh(host, user, key, cmd, timeout=30, extra_flags=None, strict=True):
    ssh_cmd = build_ssh_cmd(host, user, key, cmd, extra_flags, strict)
    return _run(ssh_cmd, timeout)


def run_ssh_with_stdin(host, user, key, stdin_data, cmd, timeout=30, strict=True):
    ssh_cmd = build_ssh_cmd(host, user, key, cmd, strict=strict)
    return _run(ssh_cmd, timeout, stdin_data)
