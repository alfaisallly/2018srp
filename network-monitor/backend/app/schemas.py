from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


CheckType = Literal["ping", "tcp", "http"]


class TargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    check_type: CheckType = "ping"
    port: int | None = Field(default=None, ge=1, le=65535)
    path: str = "/"
    interval_seconds: float = Field(default=15, ge=5, le=3600)
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return [t.strip().lower() for t in value if t and t.strip()][:12]

    @field_validator("host")
    @classmethod
    def strip_host(cls, value: str) -> str:
        return value.strip()


class TargetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    check_type: CheckType | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    path: str | None = None
    interval_seconds: float | None = Field(default=None, ge=5, le=3600)
    enabled: bool | None = None
    tags: list[str] | None = None
    notes: str | None = None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [t.strip().lower() for t in value if t and t.strip()][:12]


class TargetOut(BaseModel):
    id: int
    name: str
    host: str
    check_type: CheckType
    port: int | None = None
    path: str | None = "/"
    interval_seconds: float
    enabled: bool
    tags: list[str]
    notes: str = ""
    created_at: str
    updated_at: str
    status: str | None = None
    latest: dict[str, Any] | None = None


class DiscoverRequest(BaseModel):
    import_as_ping: bool = True
