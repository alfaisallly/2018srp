from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "NetPulse"
    database_path: Path = Path(__file__).resolve().parents[2] / "data" / "netpulse.db"
    check_interval_seconds: float = 15.0
    ping_timeout_seconds: float = 2.0
    http_timeout_seconds: float = 5.0
    tcp_timeout_seconds: float = 3.0
    history_retention: int = 500
    cors_origins: list[str] = ["*"]


settings = Settings()
