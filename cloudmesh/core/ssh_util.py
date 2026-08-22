import subprocess
import warnings


class SSHWarning(UserWarning):
    pass


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
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return str(e), 1


def run_ssh_with_stdin(host, user, key, stdin_data, cmd, timeout=30, strict=True):
    ssh_cmd = build_ssh_cmd(host, user, key, cmd, strict=strict)
    try:
        result = subprocess.run(
            ssh_cmd, input=stdin_data, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return str(e), 1
