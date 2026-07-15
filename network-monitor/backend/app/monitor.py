from __future__ import annotations

import asyncio
import platform
import re
import socket
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import settings
from .database import Database


LATENCY_RE = re.compile(r"time[=<]([\d.]+)\s*ms", re.IGNORECASE)


class MonitorEngine:
    def __init__(self, database: Database) -> None:
        self.db = database
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._running_checks: set[int] = set()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="monitor-loop")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
            self._task = None

    async def check_now(self, target_id: int | None = None) -> list[dict[str, Any]]:
        if target_id is not None:
            target = await self.db.get_target(target_id)
            if not target:
                return []
            result = await self._run_and_store(target)
            return [result]
        targets = await self.db.list_targets()
        results = []
        for target in targets:
            if not target["enabled"]:
                continue
            results.append(await self._run_and_store(target))
        return results

    async def _loop(self) -> None:
        # Kick off an immediate sweep, then keep the fleet warm.
        while not self._stop.is_set():
            try:
                targets = await self.db.list_targets()
                now = time.time()
                due = []
                for target in targets:
                    if not target["enabled"]:
                        continue
                    if target["id"] in self._running_checks:
                        continue
                    latest = await self.db.latest_check(target["id"])
                    if latest is None:
                        due.append(target)
                        continue
                    age = now - _parse_ts(latest["checked_at"])
                    if age >= float(target.get("interval_seconds") or settings.check_interval_seconds):
                        due.append(target)
                await asyncio.gather(*(self._run_and_store(t) for t in due))
            except Exception:
                # Keep the loop alive; individual checks already capture failures.
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                continue

    async def _run_and_store(self, target: dict[str, Any]) -> dict[str, Any]:
        self._running_checks.add(target["id"])
        try:
            result = await self.probe(target)
            previous = await self.db.latest_check(target["id"])
            prev_status = previous["status"] if previous else None
            await self.db.add_check(
                target["id"],
                result["status"],
                result.get("latency_ms"),
                result.get("message", ""),
            )
            if prev_status and prev_status != result["status"]:
                severity = "critical" if result["status"] == "down" else "warning"
                if result["status"] == "up":
                    severity = "info"
                title = f"{target['name']} is {result['status'].upper()}"
                detail = (
                    f"{target['host']} changed {prev_status} → {result['status']}. "
                    f"{result.get('message', '')}"
                )
                await self.db.add_alert(target["id"], severity, title, detail)
            return {**result, "target_id": target["id"], "name": target["name"]}
        finally:
            self._running_checks.discard(target["id"])

    async def probe(self, target: dict[str, Any]) -> dict[str, Any]:
        check_type = target["check_type"]
        if check_type == "ping":
            return await self._ping(target["host"])
        if check_type == "tcp":
            return await self._tcp(target["host"], int(target["port"] or 0))
        if check_type == "http":
            return await self._http(target)
        return {"status": "down", "latency_ms": None, "message": f"Unknown check type: {check_type}"}

    async def _ping(self, host: str) -> dict[str, Any]:
        system = platform.system().lower()
        if system == "windows":
            cmd = ["ping", "-n", "1", "-w", str(int(settings.ping_timeout_seconds * 1000)), host]
        else:
            # -c 1 one packet; -W timeout seconds on Linux
            cmd = ["ping", "-c", "1", "-W", str(int(max(1, settings.ping_timeout_seconds))), host]

        started = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=settings.ping_timeout_seconds + 1.5,
            )
        except (asyncio.TimeoutError, FileNotFoundError, OSError) as exc:
            # Fallback: TCP connect to common ports as soft reachability.
            soft = await self._tcp(host, 443)
            if soft["status"] == "up":
                return {
                    "status": "degraded",
                    "latency_ms": soft.get("latency_ms"),
                    "message": f"ICMP unavailable ({exc}); TCP:443 reachable",
                }
            soft80 = await self._tcp(host, 80)
            if soft80["status"] == "up":
                return {
                    "status": "degraded",
                    "latency_ms": soft80.get("latency_ms"),
                    "message": f"ICMP unavailable ({exc}); TCP:80 reachable",
                }
            return {
                "status": "down",
                "latency_ms": None,
                "message": f"Ping failed: {exc}",
            }

        output = (stdout or b"").decode(errors="ignore") + (stderr or b"").decode(errors="ignore")
        elapsed_ms = (time.perf_counter() - started) * 1000
        match = LATENCY_RE.search(output)
        latency = float(match.group(1)) if match else elapsed_ms
        if proc.returncode == 0:
            return {"status": "up", "latency_ms": round(latency, 2), "message": "ICMP reply"}
        return {
            "status": "down",
            "latency_ms": None,
            "message": output.strip().splitlines()[-1] if output.strip() else "No reply",
        }

    async def _tcp(self, host: str, port: int) -> dict[str, Any]:
        if not port:
            return {"status": "down", "latency_ms": None, "message": "Port is required for TCP checks"}
        started = time.perf_counter()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=settings.tcp_timeout_seconds,
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            latency = (time.perf_counter() - started) * 1000
            return {
                "status": "up",
                "latency_ms": round(latency, 2),
                "message": f"TCP {host}:{port} open",
            }
        except Exception as exc:
            return {
                "status": "down",
                "latency_ms": None,
                "message": f"TCP {host}:{port} failed: {exc}",
            }

    async def _http(self, target: dict[str, Any]) -> dict[str, Any]:
        host = target["host"]
        port = target.get("port")
        path = target.get("path") or "/"
        if not path.startswith("/"):
            path = "/" + path

        if host.startswith("http://") or host.startswith("https://"):
            url = host.rstrip("/") + path
        else:
            scheme = "https" if port in (443, None) else "http"
            if port and port not in (80, 443):
                url = f"{scheme}://{host}:{port}{path}"
            else:
                # Prefer https when port omitted or 443
                if port == 80:
                    url = f"http://{host}{path}"
                else:
                    url = f"https://{host}{path}"

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
                response = await client.get(url, timeout=settings.http_timeout_seconds)
            latency = (time.perf_counter() - started) * 1000
            if 200 <= response.status_code < 400:
                status = "up"
            elif 400 <= response.status_code < 500:
                status = "degraded"
            else:
                status = "down"
            return {
                "status": status,
                "latency_ms": round(latency, 2),
                "message": f"HTTP {response.status_code} from {urlparse(url).netloc}",
            }
        except Exception as exc:
            return {
                "status": "down",
                "latency_ms": None,
                "message": f"HTTP check failed: {exc}",
            }


def discover_local_hosts(limit: int = 24) -> list[dict[str, str]]:
    """Best-effort local subnet discovery via hostname + gateway-ish common IPs."""
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(name: str, host: str) -> None:
        if host in seen:
            return
        seen.add(host)
        found.append({"name": name, "host": host})

    add("localhost", "127.0.0.1")
    try:
        hostname = socket.gethostname()
        add(hostname or "this-host", socket.gethostbyname(hostname))
    except OSError:
        pass

    # Probe a small private-range slice around typical gateway addresses.
    candidates = [
        "192.168.0.1",
        "192.168.1.1",
        "10.0.0.1",
        "172.16.0.1",
    ]
    for ip in candidates:
        try:
            with socket.create_connection((ip, 80), timeout=0.35):
                add(f"gateway-ish {ip}", ip)
        except OSError:
            try:
                with socket.create_connection((ip, 443), timeout=0.35):
                    add(f"gateway-ish {ip}", ip)
            except OSError:
                continue
        if len(found) >= limit:
            break
    return found[:limit]


def _parse_ts(value: str) -> float:
    # Values are ISO-8601; handle Z vs offset.
    try:
        from datetime import datetime

        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0
