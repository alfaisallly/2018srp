from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from .config import settings


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    host TEXT NOT NULL,
    check_type TEXT NOT NULL DEFAULT 'ping',
    port INTEGER,
    path TEXT DEFAULT '/',
    interval_seconds REAL NOT NULL DEFAULT 15,
    enabled INTEGER NOT NULL DEFAULT 1,
    tags TEXT NOT NULL DEFAULT '[]',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    latency_ms REAL,
    message TEXT,
    checked_at TEXT NOT NULL,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_checks_target_time ON checks(target_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(created_at DESC);
"""


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.database_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    async def list_targets(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT * FROM targets ORDER BY name COLLATE NOCASE"
        )
        rows = await cursor.fetchall()
        return [self._target_row(row) for row in rows]

    async def get_target(self, target_id: int) -> dict[str, Any] | None:
        cursor = await self.conn.execute(
            "SELECT * FROM targets WHERE id = ?", (target_id,)
        )
        row = await cursor.fetchone()
        return self._target_row(row) if row else None

    async def create_target(self, data: dict[str, Any]) -> dict[str, Any]:
        now = utcnow()
        cursor = await self.conn.execute(
            """
            INSERT INTO targets (
                name, host, check_type, port, path, interval_seconds,
                enabled, tags, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["host"],
                data["check_type"],
                data.get("port"),
                data.get("path", "/"),
                data.get("interval_seconds", settings.check_interval_seconds),
                1 if data.get("enabled", True) else 0,
                json.dumps(data.get("tags", [])),
                data.get("notes", ""),
                now,
                now,
            ),
        )
        await self.conn.commit()
        created = await self.get_target(cursor.lastrowid)
        assert created is not None
        return created

    async def update_target(self, target_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        existing = await self.get_target(target_id)
        if existing is None:
            return None
        merged = {**existing, **data, "updated_at": utcnow()}
        await self.conn.execute(
            """
            UPDATE targets SET
                name = ?, host = ?, check_type = ?, port = ?, path = ?,
                interval_seconds = ?, enabled = ?, tags = ?, notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                merged["name"],
                merged["host"],
                merged["check_type"],
                merged.get("port"),
                merged.get("path", "/"),
                merged.get("interval_seconds", settings.check_interval_seconds),
                1 if merged.get("enabled", True) else 0,
                json.dumps(merged.get("tags", [])),
                merged.get("notes", ""),
                merged["updated_at"],
                target_id,
            ),
        )
        await self.conn.commit()
        return await self.get_target(target_id)

    async def delete_target(self, target_id: int) -> bool:
        cursor = await self.conn.execute("DELETE FROM targets WHERE id = ?", (target_id,))
        await self.conn.commit()
        return cursor.rowcount > 0

    async def add_check(
        self,
        target_id: int,
        status: str,
        latency_ms: float | None,
        message: str,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO checks (target_id, status, latency_ms, message, checked_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (target_id, status, latency_ms, message, utcnow()),
        )
        await self.conn.execute(
            """
            DELETE FROM checks WHERE id IN (
                SELECT id FROM checks
                WHERE target_id = ?
                ORDER BY checked_at DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (target_id, settings.history_retention),
        )
        await self.conn.commit()

    async def latest_check(self, target_id: int) -> dict[str, Any] | None:
        cursor = await self.conn.execute(
            """
            SELECT * FROM checks
            WHERE target_id = ?
            ORDER BY checked_at DESC
            LIMIT 1
            """,
            (target_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def check_history(self, target_id: int, limit: int = 100) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            """
            SELECT * FROM checks
            WHERE target_id = ?
            ORDER BY checked_at DESC
            LIMIT ?
            """,
            (target_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def previous_status(self, target_id: int) -> str | None:
        cursor = await self.conn.execute(
            """
            SELECT status FROM checks
            WHERE target_id = ?
            ORDER BY checked_at DESC
            LIMIT 1 OFFSET 1
            """,
            (target_id,),
        )
        row = await cursor.fetchone()
        return row["status"] if row else None

    async def add_alert(
        self,
        target_id: int,
        severity: str,
        title: str,
        detail: str,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO alerts (target_id, severity, title, detail, created_at, acknowledged)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (target_id, severity, title, detail, utcnow()),
        )
        await self.conn.commit()

    async def list_alerts(self, limit: int = 50, unacked_only: bool = False) -> list[dict[str, Any]]:
        query = """
            SELECT a.*, t.name AS target_name, t.host AS target_host
            FROM alerts a
            JOIN targets t ON t.id = a.target_id
        """
        if unacked_only:
            query += " WHERE a.acknowledged = 0"
        query += " ORDER BY a.created_at DESC LIMIT ?"
        cursor = await self.conn.execute(query, (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def acknowledge_alert(self, alert_id: int) -> bool:
        cursor = await self.conn.execute(
            "UPDATE alerts SET acknowledged = 1 WHERE id = ?",
            (alert_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def overview(self) -> dict[str, Any]:
        targets = await self.list_targets()
        statuses = {"up": 0, "down": 0, "degraded": 0, "unknown": 0, "disabled": 0}
        enriched = []
        for target in targets:
            if not target["enabled"]:
                statuses["disabled"] += 1
                status = "disabled"
                latest = None
            else:
                latest = await self.latest_check(target["id"])
                status = latest["status"] if latest else "unknown"
                statuses[status] = statuses.get(status, 0) + 1
            enriched.append({**target, "latest": latest, "status": status})

        cursor = await self.conn.execute(
            "SELECT COUNT(*) AS c FROM alerts WHERE acknowledged = 0"
        )
        unacked = (await cursor.fetchone())["c"]
        return {
            "counts": statuses,
            "open_alerts": unacked,
            "targets": enriched,
            "generated_at": utcnow(),
        }

    async def seed_defaults(self) -> None:
        cursor = await self.conn.execute("SELECT COUNT(*) AS c FROM targets")
        count = (await cursor.fetchone())["c"]
        if count:
            return
        defaults = [
            {
                "name": "Local loopback",
                "host": "127.0.0.1",
                "check_type": "ping",
                "tags": ["local", "core"],
                "notes": "Always-on baseline for the monitoring host",
            },
            {
                "name": "Cloudflare DNS",
                "host": "1.1.1.1",
                "check_type": "ping",
                "tags": ["dns", "internet"],
                "notes": "Public DNS reachability",
            },
            {
                "name": "Google DNS",
                "host": "8.8.8.8",
                "check_type": "ping",
                "tags": ["dns", "internet"],
            },
            {
                "name": "Example HTTPS",
                "host": "example.com",
                "check_type": "http",
                "port": 443,
                "path": "/",
                "tags": ["web", "external"],
                "notes": "External HTTP(S) probe",
            },
            {
                "name": "Local API",
                "host": "127.0.0.1",
                "check_type": "tcp",
                "port": 8080,
                "tags": ["local", "api"],
                "notes": "NetPulse API listener",
            },
            {
                "name": "GitHub",
                "host": "github.com",
                "check_type": "http",
                "port": 443,
                "path": "/",
                "tags": ["web", "scm"],
            },
        ]
        for item in defaults:
            await self.create_target(item)

    @staticmethod
    def _target_row(row: aiosqlite.Row) -> dict[str, Any]:
        data = dict(row)
        data["enabled"] = bool(data["enabled"])
        data["tags"] = json.loads(data.get("tags") or "[]")
        return data


db = Database()
