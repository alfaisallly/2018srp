from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import AlertSeverity, AlertStatus, DeviceStatus, Permission, ProtocolType, VendorType


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    role: str = "viewer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime


class DataCenterCreate(BaseModel):
    name: str
    location: str | None = None
    description: str | None = None
    contact_email: EmailStr | None = None


class DataCenterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str | None
    description: str | None
    contact_email: str | None
    created_at: datetime


class RackCreate(BaseModel):
    name: str
    row: str | None = None
    capacity_u: int = 42


class RackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    datacenter_id: int
    name: str
    row: str | None
    capacity_u: int


class DeviceCredentialCreate(BaseModel):
    protocol: ProtocolType
    username: str | None = None
    password: str | None = None
    community: str | None = None
    api_token: str | None = None
    port: int | None = None


class DeviceCreate(BaseModel):
    datacenter_id: int
    rack_id: int | None = None
    name: str
    hostname: str
    ip_address: str
    vendor: VendorType
    model: str | None = None
    position_u: int | None = None
    height_u: int = 1
    tags: dict | None = None
    credentials: list[DeviceCredentialCreate] = []


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    datacenter_id: int
    rack_id: int | None
    name: str
    hostname: str
    ip_address: str
    vendor: VendorType
    model: str | None
    serial_number: str | None
    status: DeviceStatus
    position_u: int | None
    height_u: int
    tags: dict | None
    last_seen: datetime | None
    created_at: datetime


class NetworkMapCreate(BaseModel):
    datacenter_id: int
    name: str
    description: str | None = None
    topology: dict = Field(default_factory=dict)


class NetworkMapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    datacenter_id: int
    name: str
    description: str | None
    topology: dict
    created_at: datetime
    updated_at: datetime


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int | None
    datacenter_id: int | None
    title: str
    message: str
    severity: AlertSeverity
    status: AlertStatus
    source: str
    created_at: datetime
    resolved_at: datetime | None


class AlertUpdate(BaseModel):
    status: AlertStatus


class DashboardStats(BaseModel):
    datacenters: int
    total_devices: int
    online_devices: int
    offline_devices: int
    open_alerts: int
    critical_alerts: int


class PollResult(BaseModel):
    success: bool
    protocol: str | None = None
    hostname: str | None = None
    error: str | None = None
