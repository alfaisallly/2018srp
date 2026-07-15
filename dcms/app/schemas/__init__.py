from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import AlertSeverity, AlertStatus, DeviceStatus, Permission, ProtocolType, ServerOSType, ServerRole, StorageType, StorageVendor, VendorType


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    role: str = "viewer"
    permissions: list[str] | None = None
    is_active: bool = True


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    full_name: str | None = None
    role: str | None = None
    permissions: list[str] | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str | None
    role: str
    permissions: list[str] | None = None
    is_active: bool
    created_at: datetime


class PermissionInfo(BaseModel):
    key: str
    label: str
    group: str
    description: str


class RoleTemplate(BaseModel):
    key: str
    label: str
    permissions: list[str]


class MeResponse(UserResponse):
    permission_keys: list[str] = []


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
    total_servers: int = 0
    online_servers: int = 0
    total_storage: int = 0
    online_storage: int = 0
    open_alerts: int
    critical_alerts: int


class PollResult(BaseModel):
    success: bool
    protocol: str | None = None
    hostname: str | None = None
    error: str | None = None


class DiscoverRequest(BaseModel):
    datacenter_id: int | None = None
    cidr: str | None = Field(default=None, examples=["192.168.10.0/24"])
    start_ip: str | None = None
    end_ip: str | None = None
    community: str = "public"
    port: int = 161
    max_hosts: int = Field(default=254, le=1024)


class DiscoveredDeviceResponse(BaseModel):
    ip_address: str
    hostname: str
    sys_descr: str
    vendor: VendorType
    model: str | None = None


class DiscoverResponse(BaseModel):
    scanned: int
    found: int
    devices: list[DiscoveredDeviceResponse]


class ImportDiscoveredRequest(BaseModel):
    datacenter_id: int
    community: str = "public"
    port: int = 161
    ips: list[str]
    poll_after_import: bool = True


class ImportDiscoveredResponse(BaseModel):
    imported: int
    skipped: int
    device_ids: list[int]


class AssetCredentialCreate(BaseModel):
    protocol: ProtocolType
    username: str | None = None
    password: str | None = None
    community: str | None = None
    api_token: str | None = None
    port: int | None = None


class ServerCreate(BaseModel):
    datacenter_id: int
    rack_id: int | None = None
    name: str
    hostname: str
    ip_address: str
    os_type: ServerOSType
    server_role: ServerRole = ServerRole.OTHER
    cpu_cores: int | None = None
    ram_gb: int | None = None
    position_u: int | None = None
    notes: str | None = None
    credentials: list[AssetCredentialCreate] = []


class ServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    datacenter_id: int
    rack_id: int | None
    name: str
    hostname: str
    ip_address: str
    os_type: ServerOSType
    server_role: ServerRole
    cpu_cores: int | None
    ram_gb: int | None
    status: DeviceStatus
    position_u: int | None
    notes: str | None
    last_seen: datetime | None
    created_at: datetime


class StorageCreate(BaseModel):
    datacenter_id: int
    rack_id: int | None = None
    name: str
    hostname: str
    ip_address: str
    vendor: StorageVendor
    model: str | None = None
    storage_type: StorageType = StorageType.OTHER
    total_capacity_tb: float | None = None
    position_u: int | None = None
    notes: str | None = None
    credentials: list[AssetCredentialCreate] = []


class StorageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    datacenter_id: int
    rack_id: int | None
    name: str
    hostname: str
    ip_address: str
    vendor: StorageVendor
    storage_type: StorageType
    total_capacity_tb: float | None
    used_capacity_tb: float | None
    status: DeviceStatus
    position_u: int | None
    notes: str | None
    last_seen: datetime | None
    created_at: datetime


class ServerPollResult(BaseModel):
    success: bool
    protocol: str | None = None
    hostname: str | None = None
    metrics: int | None = None
    error: str | None = None


class StoragePollResult(BaseModel):
    success: bool
    protocol: str | None = None
    hostname: str | None = None
    capacity_usage_pct: float | None = None
    error: str | None = None


class MonitoringGuide(BaseModel):
    asset_type: str
    protocols: list[dict]


class ExcelAssetPreview(BaseModel):
    row: int
    datacenter: str
    asset_type: str
    name: str
    ip_address: str
    vendor: str | None = None
    protocol: str | None = None


class ExcelLinkPreview(BaseModel):
    row: int
    datacenter: str
    from_name: str = Field(alias="from")
    to_name: str = Field(alias="to")
    label: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class ExcelImportPreview(BaseModel):
    summary: dict[str, int]
    datacenters: list[str]
    errors: list[str]
    assets: list[ExcelAssetPreview]
    links: list[ExcelLinkPreview]


class ExcelApplyRequest(BaseModel):
    skip_existing: bool = True


class ExcelImportResult(BaseModel):
    imported: int
    skipped: int
    datacenters: int
    maps_updated: int
    errors: list[str]
