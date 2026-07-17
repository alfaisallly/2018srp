from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DCMS"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str = "dev-secret-key-change-in-production"

    database_url: str = "postgresql+asyncpg://dcms:dcms_password@localhost:5432/dcms"
    redis_url: str = "redis://localhost:6379/0"

    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    poll_interval_seconds: int = 300
    snmp_timeout: int = 10
    ssh_timeout: int = 30

    alert_email_from: str = "dcms@example.com"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
