import asyncio
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    DeviceStatus,
    ProtocolType,
    Server,
    ServerMetric,
    ServerOSType,
)
from app.services.snmp_collector import snmp_get_bulk
from app.services.ssh_connector import run_ssh_command


async def poll_server(db: AsyncSession, server_id: int) -> dict:
    result = await db.execute(
        select(Server).options(selectinload(Server.credentials)).where(Server.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        return {"success": False, "error": "Server not found"}

    protocol_used = None
    error = None
    metrics_collected = []

    for cred in server.credentials:
        try:
            if cred.protocol == ProtocolType.SSH and cred.username and cred.password:
                metrics_collected = await _poll_ssh(server, cred.username, cred.password, cred.port or 22)
                protocol_used = "ssh"
                break
            if cred.protocol == ProtocolType.SNMP and cred.community:
                metrics_collected = await _poll_snmp(server.ip_address, cred.community, cred.port or 161)
                protocol_used = "snmp"
                break
            if cred.protocol == ProtocolType.REST and cred.api_token:
                metrics_collected = await _poll_vmware_rest(
                    server.ip_address, cred.username or "", cred.password or "", cred.api_token, cred.port or 443
                )
                protocol_used = "rest"
                break
            if cred.protocol == ProtocolType.WINRM and cred.username and cred.password:
                metrics_collected = await _poll_winrm(server.ip_address, cred.username, cred.password, cred.port or 5985)
                protocol_used = "winrm"
                break
            if cred.protocol == ProtocolType.IPMI and cred.username and cred.password:
                metrics_collected = await _poll_ipmi(server.ip_address, cred.username, cred.password, cred.port or 623)
                protocol_used = "ipmi"
                break
        except Exception as exc:
            error = str(exc)
            continue

    if metrics_collected or protocol_used:
        server.status = DeviceStatus.ONLINE
        server.last_seen = datetime.now(timezone.utc)
        for name, value, unit in metrics_collected:
            db.add(ServerMetric(server_id=server.id, metric_name=name, metric_value=value, unit=unit))
        await _check_server_thresholds(db, server, metrics_collected)
        await db.flush()
        return {"success": True, "protocol": protocol_used, "hostname": server.hostname, "metrics": len(metrics_collected)}

    server.status = DeviceStatus.OFFLINE
    await db.flush()
    await _create_server_alert(
        db, server, f"Server unreachable: {server.name}", error or "All protocols failed", AlertSeverity.CRITICAL
    )
    return {"success": False, "error": error or "All protocols failed"}


async def _poll_ssh(server: Server, username: str, password: str, port: int) -> list[tuple[str, float, str | None]]:
    if server.os_type == ServerOSType.WINDOWS:
        cmd = "systeminfo | findstr /B /C:\"Total Physical Memory\""
        output = await asyncio.to_thread(run_ssh_command, server.ip_address, username, password, cmd, port)
        metrics = [("reachable", 1.0, "bool")]
        mem_match = re.search(r"(\d+)", output.replace(",", ""))
        if mem_match:
            metrics.append(("memory_total_mb", float(mem_match.group(1)), "MB"))
        return metrics

    commands = "uptime; free -m | awk '/Mem:/ {print $3,$2}'; df -h / | awk 'NR==2 {print $5}' | tr -d '%'"
    output = await asyncio.to_thread(run_ssh_command, server.ip_address, username, password, commands, port)
    lines = [l.strip() for l in output.strip().split("\n") if l.strip()]
    metrics: list[tuple[str, float, str | None]] = [("reachable", 1.0, "bool")]

    load_match = re.search(r"load average:\s*([\d.]+)", output)
    if load_match:
        metrics.append(("load_1m", float(load_match.group(1)), "load"))

    if len(lines) >= 2:
        mem_parts = lines[1].split()
        if len(mem_parts) == 2:
            used, total = float(mem_parts[0]), float(mem_parts[1])
            metrics.append(("memory_used_mb", used, "MB"))
            metrics.append(("memory_total_mb", total, "MB"))
            if total > 0:
                metrics.append(("memory_usage", (used / total) * 100, "%"))

    if len(lines) >= 3:
        try:
            metrics.append(("disk_usage_root", float(lines[2]), "%"))
        except ValueError:
            pass

    return metrics


async def _poll_snmp(host: str, community: str, port: int) -> list[tuple[str, float, str | None]]:
    oids = {
        "cpu": "1.3.6.1.2.1.25.3.3.1.2.1",
        "mem_total": "1.3.6.1.2.1.25.2.3.0",
    }
    data = await asyncio.to_thread(snmp_get_bulk, host, community, oids, port)
    metrics: list[tuple[str, float, str | None]] = [("reachable", 1.0, "bool")]
    if "cpu" in data:
        try:
            metrics.append(("cpu_utilization", float(data["cpu"]), "%"))
        except ValueError:
            pass
    return metrics


async def _poll_vmware_rest(host: str, username: str, password: str, token: str, port: int) -> list[tuple[str, float, str | None]]:
    from app.services.rest_api_connector import rest_get

    data = await rest_get(host, "/rest/appliance/system/version", token, port, verify_ssl=False)
    version = data.get("version", "unknown") if isinstance(data, dict) else "unknown"
    return [("reachable", 1.0, "bool"), ("esxi_version", hash(version) % 1000, "info")]


async def _poll_winrm(host: str, username: str, password: str, port: int) -> list[tuple[str, float, str | None]]:
    try:
        import winrm  # noqa: F401
    except ImportError:
        return [("reachable", 0.0, "bool")]

    import winrm

    session = winrm.Session(f"http://{host}:{port}/wsman", auth=(username, password), transport="ntlm")
    result = session.run_cmd("wmic cpu get loadpercentage")
    output = result.std_out.decode("utf-8", errors="replace")
    metrics: list[tuple[str, float, str | None]] = [("reachable", 1.0, "bool")]
    for line in output.splitlines():
        line = line.strip()
        if line.isdigit():
            metrics.append(("cpu_utilization", float(line), "%"))
            break
    return metrics


async def _poll_ipmi(host: str, username: str, password: str, port: int) -> list[tuple[str, float, str | None]]:
    import shutil
    import subprocess

    if not shutil.which("ipmitool"):
        return [("reachable", 0.0, "bool"), ("ipmi_configured", 0.0, "bool")]

    def _run() -> str:
        return subprocess.run(
            ["ipmitool", "-I", "lanplus", "-H", host, "-p", str(port), "-U", username, "-P", password, "sensor", "list"],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout

    output = await asyncio.to_thread(_run)
    ok = bool(output.strip())
    return [("reachable", 1.0 if ok else 0.0, "bool"), ("ipmi_sensors", float(output.count("\n")), "count")]


async def _check_server_thresholds(db: AsyncSession, server: Server, metrics: list[tuple[str, float, str | None]]) -> None:
    for name, value, unit in metrics:
        if name == "cpu_utilization" and value > 90:
            await _create_server_alert(db, server, f"High CPU on {server.name}", f"CPU {value}%", AlertSeverity.WARNING)
        if name == "memory_usage" and value > 90:
            await _create_server_alert(db, server, f"High memory on {server.name}", f"Memory {value}%", AlertSeverity.WARNING)
        if name == "disk_usage_root" and value > 90:
            await _create_server_alert(db, server, f"High disk on {server.name}", f"Disk {value}%", AlertSeverity.WARNING)


async def _create_server_alert(db: AsyncSession, server: Server, title: str, message: str, severity: AlertSeverity) -> None:
    existing = await db.execute(
        select(Alert).where(
            Alert.server_id == server.id,
            Alert.title == title,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
        )
    )
    if existing.scalar_one_or_none():
        return
    db.add(
        Alert(
            server_id=server.id,
            datacenter_id=server.datacenter_id,
            title=title,
            message=message,
            severity=severity,
            source="server_monitor",
        )
    )


async def poll_all_servers(db: AsyncSession) -> dict:
    result = await db.execute(select(Server.id))
    ids = [row[0] for row in result.all()]
    stats = {"total": len(ids), "online": 0, "offline": 0}
    for sid in ids:
        r = await poll_server(db, sid)
        if r.get("success"):
            stats["online"] += 1
        else:
            stats["offline"] += 1
    return stats
