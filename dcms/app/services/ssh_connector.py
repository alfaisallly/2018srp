import paramiko

from app.config import get_settings

settings = get_settings()


def run_ssh_command(
    host: str,
    username: str,
    password: str,
    command: str,
    port: int = 22,
) -> str:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=settings.ssh_timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        _, stdout, stderr = client.exec_command(command, timeout=settings.ssh_timeout)
        output = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return output or err
    finally:
        client.close()


def run_ssh_commands(
    host: str,
    username: str,
    password: str,
    commands: list[str],
    port: int = 22,
) -> dict[str, str]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    results: dict[str, str] = {}
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=settings.ssh_timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        for command in commands:
            _, stdout, stderr = client.exec_command(command, timeout=settings.ssh_timeout)
            output = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            results[command] = output or err
    finally:
        client.close()
    return results
