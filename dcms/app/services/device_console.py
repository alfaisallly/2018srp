"""Live SSH console: test connection, execute commands, and push configuration."""

import asyncio
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Device, DeviceCredential, ProtocolType, VendorType

CONSOLE_VENDORS = {
    VendorType.CISCO,
    VendorType.JUNIPER,
    VendorType.PALO_ALTO,
    VendorType.FORTINET,
}

TEST_COMMANDS = {
    VendorType.CISCO: "show version",
    VendorType.JUNIPER: "show version",
    VendorType.PALO_ALTO: "show system info",
    VendorType.FORTINET: "get system status",
}


def resolve_ssh_cred(device: Device) -> DeviceCredential | None:
    return next(
        (c for c in device.credentials if c.protocol == ProtocolType.SSH and c.username and c.password),
        None,
    )


def _parse_test_output(vendor: VendorType, host: str, output: str) -> dict:
    hostname = host
    model = None
    os_version = None
    if vendor == VendorType.CISCO:
        if m := re.search(r"(\S+) uptime is", output):
            hostname = m.group(1)
        if m := re.search(r"cisco (\S+)", output, re.IGNORECASE):
            model = m.group(1)
        os_version = output.split("\n")[0][:128] if output else None
    elif vendor == VendorType.JUNIPER:
        if m := re.search(r"Hostname:\s+(\S+)", output):
            hostname = m.group(1)
        if m := re.search(r"Model:\s+(\S+)", output):
            model = m.group(1)
        if m := re.search(r"Junos:\s+(.+)", output):
            os_version = m.group(1).strip()[:128]
    elif vendor == VendorType.PALO_ALTO:
        for line in output.splitlines():
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if key == "hostname":
                hostname = val
            elif key == "model":
                model = val
            elif key == "sw-version":
                os_version = val
    elif vendor == VendorType.FORTINET:
        if m := re.search(r"Hostname:\s+(\S+)", output):
            hostname = m.group(1)
        if m := re.search(r"Version:\s+(.+)", output):
            os_version = m.group(1).strip()[:128]
    return {"hostname": hostname, "model": model, "os_version": os_version}


def wrap_config_push(vendor: VendorType, config_text: str) -> str:
    lines = [ln.rstrip() for ln in config_text.strip().splitlines() if ln.strip()]
    body = "\n".join(lines)
    if vendor == VendorType.CISCO:
        return f"configure terminal\n{body}\nend"
    if vendor == VendorType.JUNIPER:
        if all(ln.startswith(("set ", "delete ", "activate ", "deactivate ")) for ln in lines):
            return f"configure private\n{body}\ncommit and-quit"
        return body
    if vendor == VendorType.PALO_ALTO:
        return f"configure\n{body}\ncommit\nexit"
    if vendor == VendorType.FORTINET:
        return body
    return body


async def test_connection(
    host: str,
    vendor: VendorType,
    username: str,
    password: str,
    port: int = 22,
) -> dict:
    if vendor not in CONSOLE_VENDORS:
        return {"ok": False, "message": f"Unsupported vendor: {vendor.value}"}
    cmd = TEST_COMMANDS.get(vendor, "show version")
    from app.services.ssh_connector import run_ssh_command

    try:
        output = await asyncio.to_thread(run_ssh_command, host, username, password, cmd, port)
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    if not output or not output.strip():
        return {"ok": False, "message": "Empty response from device"}
    parsed = _parse_test_output(vendor, host, output)
    return {
        "ok": True,
        "hostname": parsed["hostname"],
        "model": parsed["model"],
        "os_version": parsed["os_version"],
        "message": "Connection successful",
        "preview": output[:1500],
    }


async def execute_command(
    host: str,
    vendor: VendorType,
    username: str,
    password: str,
    command: str,
    port: int = 22,
    mode: str = "exec",
) -> dict:
    if not command or not command.strip():
        raise ValueError("Command is required")
    from app.services.ssh_connector import run_ssh_command

    payload = wrap_config_push(vendor, command) if mode == "config" else command.strip()
    try:
        output = await asyncio.to_thread(run_ssh_command, host, username, password, payload, port)
        return {"ok": True, "command": command.strip(), "output": output, "error": None}
    except Exception as exc:
        return {"ok": False, "command": command.strip(), "output": "", "error": str(exc)}


async def execute_on_device(
    session: AsyncSession,
    device_id: int,
    command: str,
    mode: str = "exec",
) -> dict:
    result = await session.execute(
        select(Device).options(selectinload(Device.credentials)).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise ValueError("Device not found")
    if device.vendor not in CONSOLE_VENDORS:
        raise ValueError(f"Console not supported for vendor {device.vendor.value}")
    cred = resolve_ssh_cred(device)
    if not cred:
        raise ValueError("SSH credentials required — add SSH username/password to the device")
    port = cred.port or 22
    data = await execute_command(
        device.ip_address,
        device.vendor,
        cred.username,
        cred.password,
        command,
        port,
        mode,
    )
    data["device_id"] = device_id
    data["device_name"] = device.name
    data["host"] = device.ip_address
    return data


async def apply_config_text(
    session: AsyncSession,
    device_id: int,
    config_text: str,
) -> dict:
    return await execute_on_device(session, device_id, config_text, mode="config")
