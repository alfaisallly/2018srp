from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import (
    AlertSeverity,
    AlertStatus,
    DeviceStatus,
    DeviceType,
    IntegrationType,
    IpAddressStatus,
    Permission,
    ProtocolType,
    ServerOSType,
    ServerRole,
    StorageType,
    StorageVendor,
    VendorType,
)


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


class DataCenterOverviewSummary(BaseModel):
    switches: int = 0
    firewalls: int = 0
    routers: int = 0
    other_devices: int = 0
    total_devices: int = 0
    online_devices: int = 0
    servers: int = 0
    online_servers: int = 0
    storage: int = 0
    online_storage: int = 0
    open_alerts: int = 0
    critical_alerts: int = 0
    network_maps: int = 0
    total_sensors: int = 0
    sensors_up: int = 0
    sensors_warning: int = 0
    sensors_down: int = 0


class DataCenterAssetBrief(BaseModel):
    id: int
    name: str
    hostname: str
    ip_address: str
    vendor: str | None = None
    device_type: str | None = None
    model: str | None = None
    os_type: str | None = None
    server_role: str | None = None
    storage_type: str | None = None
    total_capacity_tb: float | None = None
    used_capacity_tb: float | None = None
    status: str
    last_seen: datetime | None = None


class DataCenterAlertBrief(BaseModel):
    id: int
    title: str
    message: str
    severity: str
    status: str
    source: str
    created_at: datetime


class DataCenterSensorBrief(BaseModel):
    id: int
    name: str
    asset_type: str
    metric_key: str
    last_value: float | None = None
    unit: str | None = None
    last_status: str
    status_color: str
    status_label: str
    last_check_at: datetime | None = None


class DataCenterMapBrief(BaseModel):
    id: int
    name: str
    description: str | None = None
    topology: dict = Field(default_factory=dict)
    updated_at: datetime


class DataCenterOverview(BaseModel):
    datacenter: DataCenterResponse
    summary: DataCenterOverviewSummary
    switches: list[DataCenterAssetBrief]
    firewalls: list[DataCenterAssetBrief]
    routers: list[DataCenterAssetBrief]
    other_devices: list[DataCenterAssetBrief]
    servers: list[DataCenterAssetBrief]
    storage: list[DataCenterAssetBrief]
    network_maps: list[DataCenterMapBrief]
    alerts: list[DataCenterAlertBrief]
    sensors: list[DataCenterSensorBrief]


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
    device_type: DeviceType = DeviceType.SWITCH
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
    device_type: DeviceType
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
    server_id: int | None = None
    storage_id: int | None = None
    sensor_id: int | None = None
    datacenter_id: int | None
    title: str
    message: str
    severity: AlertSeverity
    status: AlertStatus
    source: str = "system"
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
    total_sensors: int = 0
    sensors_up: int = 0
    sensors_warning: int = 0
    sensors_down: int = 0


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


class SensorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    datacenter_id: int
    asset_type: str
    asset_id: int
    asset_name: str | None = None
    device_id: int | None = None
    server_id: int | None = None
    storage_id: int | None = None
    name: str
    metric_key: str
    unit: str | None = None
    warning_limit: float | None = None
    error_limit: float | None = None
    higher_is_worse: bool = True
    enabled: bool = True
    last_value: float | None = None
    last_status: str
    last_message: str | None = None
    last_check_at: datetime | None = None
    status_color: str
    status_label: str
    created_at: datetime


class SensorUpdate(BaseModel):
    name: str | None = None
    warning_limit: float | None = None
    error_limit: float | None = None
    higher_is_worse: bool | None = None
    enabled: bool | None = None
    unit: str | None = None


class SensorSummary(BaseModel):
    total: int = 0
    up: int = 0
    warning: int = 0
    down: int = 0
    paused: int = 0
    unknown: int = 0


class SensorHistoryPoint(BaseModel):
    value: float
    unit: str | None = None
    collected_at: datetime


class SensorTemplatesResponse(BaseModel):
    templates: dict
    status_colors: dict


class IpPrefixCreate(BaseModel):
    datacenter_id: int
    cidr: str
    vlan: int | None = None
    gateway: str | None = None
    description: str | None = None
    dns_servers: list[str] | None = None


class IpPrefixUpdate(BaseModel):
    vlan: int | None = None
    gateway: str | None = None
    description: str | None = None
    dns_servers: list[str] | None = None


class IpPrefixResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    datacenter_id: int
    cidr: str
    vlan: int | None
    gateway: str | None
    description: str | None
    dns_servers: list | None
    created_at: datetime


class IpAddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prefix_id: int
    address: str
    status: IpAddressStatus
    hostname: str | None
    asset_type: str | None
    asset_id: int | None
    device_id: int | None
    notes: str | None
    updated_at: datetime


class IpAddressUpdate(BaseModel):
    status: IpAddressStatus | None = None
    hostname: str | None = None
    notes: str | None = None


class IpPrefixUtilization(BaseModel):
    total: int
    assigned: int
    reserved: int
    free: int
    utilization_pct: float


class IpConflictItem(BaseModel):
    ip_address: str
    assets: list[dict]


class IpSyncResult(BaseModel):
    created: int
    updated: int
    total_hosts: int


class ConfigBackupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    protocol: ProtocolType
    content_hash: str
    size_bytes: int
    collected_at: datetime


class ConfigBackupDetail(ConfigBackupResponse):
    content: str


class ConfigBackupRunResult(BaseModel):
    success: int
    unchanged: int
    failed: int
    errors: list[str] = Field(default_factory=list)


class IntegrationCreate(BaseModel):
    datacenter_id: int | None = None
    name: str
    integration_type: IntegrationType
    base_url: str
    username: str | None = None
    api_token: str | None = None
    enabled: bool = True
    extra: dict | None = None


class IntegrationUpdate(BaseModel):
    datacenter_id: int | None = None
    name: str | None = None
    base_url: str | None = None
    username: str | None = None
    api_token: str | None = None
    enabled: bool | None = None
    extra: dict | None = None


class IntegrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    datacenter_id: int | None
    name: str
    integration_type: IntegrationType
    base_url: str
    username: str | None
    enabled: bool
    extra: dict | None
    last_sync_at: datetime | None
    last_sync_status: str | None
    created_at: datetime


class IntegrationTestResult(BaseModel):
    ok: bool
    version: str | None = None
    message: str


class CapabilityModule(BaseModel):
    id: str
    icon: str
    title_key: str
    description_key: str
    enabled: bool
    active: bool


class CapabilitiesResponse(BaseModel):
    modules: list[CapabilityModule]
    metrics: dict[str, int]


class NetworkOverviewResponse(BaseModel):
    ports_total: int = 0
    ports_up: int = 0
    ports_down: int = 0
    vlans_total: int = 0
    links_total: int = 0
    firewall_rules_total: int = 0
    branch_sites_total: int = 0


class SwitchPortResponse(BaseModel):
    id: int
    device_id: int
    name: str
    port_index: int | None = None
    description: str | None = None
    oper_status: str
    admin_status: str
    speed_mbps: int | None = None
    duplex: str | None = None
    vlan_mode: str
    access_vlan: int | None = None
    trunk_vlans: list | None = None
    connected_device_id: int | None = None
    connected_device_name: str | None = None
    connected_port_name: str | None = None
    link_type: str | None = None
    ip_address: str | None = None
    services: list | None = None
    settings: dict | None = None
    last_sync_at: datetime | None = None


class DeviceVlanResponse(BaseModel):
    id: int
    datacenter_id: int
    device_id: int | None = None
    device_name: str | None = None
    vlan_id: int
    name: str
    subnet: str | None = None
    gateway: str | None = None
    status: str
    description: str | None = None
    port_count: int = 0


class NetworkLinkResponse(BaseModel):
    id: int
    datacenter_id: int
    from_device_id: int
    from_device_name: str
    from_port: str
    to_device_id: int
    to_device_name: str
    to_port: str
    link_type: str
    is_primary: bool
    bandwidth_mbps: int | None = None
    status: str
    description: str | None = None


class BranchSiteResponse(BaseModel):
    id: int
    datacenter_id: int
    name: str
    location: str | None = None
    address: str | None = None
    primary_device_id: int | None = None
    primary_device_name: str | None = None
    primary_port: str | None = None
    primary_link_type: str
    backup_enabled: bool
    backup_link_type: str | None = None
    backup_device_id: int | None = None
    backup_device_name: str | None = None
    backup_port: str | None = None
    backup_wireless_ssid: str | None = None
    status: str
    notes: str | None = None


class FirewallRuleResponse(BaseModel):
    id: int
    device_id: int
    device_name: str
    rule_id: str | None = None
    name: str
    action: str
    source: str | None = None
    destination: str | None = None
    service: str | None = None
    protocol: str | None = None
    port: str | None = None
    zone_in: str | None = None
    zone_out: str | None = None
    enabled: bool
    hit_count: int = 0
    order_index: int = 0


class TopologyResponse(BaseModel):
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class ConfigTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor: VendorType
    category: str
    name: str
    description: str | None = None
    template_body: str
    variables: list | None = None
    tags: list | None = None
    is_builtin: bool
    created_at: datetime


class ConfigTemplateRenderRequest(BaseModel):
    variables: dict = Field(default_factory=dict)


class ConfigTemplateRenderResponse(BaseModel):
    template_id: int
    template_name: str
    vendor: str
    config: str
