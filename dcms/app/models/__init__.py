import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _enum_values(enum_cls: type) -> list[str]:
    return [member.value for member in enum_cls]


class VendorType(str, enum.Enum):
    CISCO = "cisco"
    JUNIPER = "juniper"
    FORTINET = "fortinet"
    PALO_ALTO = "palo_alto"
    GENERIC = "generic"


class DeviceType(str, enum.Enum):
    SWITCH = "switch"
    FIREWALL = "firewall"
    ROUTER = "router"
    OTHER = "other"


class DeviceStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ProtocolType(str, enum.Enum):
    SNMP = "snmp"
    SSH = "ssh"
    NETCONF = "netconf"
    REST = "rest"
    IPMI = "ipmi"
    WINRM = "winrm"


class ServerOSType(str, enum.Enum):
    LINUX = "linux"
    WINDOWS = "windows"
    VMWARE = "vmware"
    OTHER = "other"


class ServerRole(str, enum.Enum):
    APPLICATION = "application"
    DATABASE = "database"
    WEB = "web"
    HYPERVISOR = "hypervisor"
    OTHER = "other"


class StorageVendor(str, enum.Enum):
    PURE_STORAGE = "pure_storage"
    NETAPP = "netapp"
    DELL_EMC = "dell_emc"
    HPE = "hpe"
    QNAP = "qnap"
    SYNOLOGY = "synology"
    GENERIC = "generic"


class StorageType(str, enum.Enum):
    SAN = "san"
    NAS = "nas"
    OBJECT = "object"
    OTHER = "other"


class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class SensorAssetType(str, enum.Enum):
    DEVICE = "device"
    SERVER = "server"
    STORAGE = "storage"


class SensorStatus(str, enum.Enum):
    UP = "up"
    WARNING = "warning"
    DOWN = "down"
    PAUSED = "paused"
    UNKNOWN = "unknown"


class Permission(str, enum.Enum):
    VIEW = "view"
    MANAGE_DEVICES = "manage_devices"
    MANAGE_DATACENTERS = "manage_datacenters"
    MANAGE_USERS = "manage_users"
    VIEW_REPORTS = "view_reports"
    MANAGE_ALERTS = "manage_alerts"
    MANAGE_NETWORK_MAPS = "manage_network_maps"
    MANAGE_SERVERS = "manage_servers"
    MANAGE_STORAGE = "manage_storage"
    MANAGE_IPAM = "manage_ipam"
    MANAGE_INTEGRATIONS = "manage_integrations"


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "admin": set(Permission),
    "operator": {
        Permission.VIEW,
        Permission.MANAGE_DEVICES,
        Permission.MANAGE_SERVERS,
        Permission.MANAGE_STORAGE,
        Permission.MANAGE_ALERTS,
        Permission.VIEW_REPORTS,
        Permission.MANAGE_NETWORK_MAPS,
        Permission.MANAGE_IPAM,
        Permission.MANAGE_INTEGRATIONS,
    },
    "viewer": {Permission.VIEW, Permission.VIEW_REPORTS},
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    permissions: Mapped[list | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DataCenter(Base):
    __tablename__ = "datacenters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    location: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    racks: Mapped[list["Rack"]] = relationship(back_populates="datacenter", cascade="all, delete-orphan")
    devices: Mapped[list["Device"]] = relationship(back_populates="datacenter", cascade="all, delete-orphan")
    servers: Mapped[list["Server"]] = relationship(back_populates="datacenter", cascade="all, delete-orphan")
    storage_systems: Mapped[list["StorageSystem"]] = relationship(back_populates="datacenter", cascade="all, delete-orphan")
    network_maps: Mapped[list["NetworkMap"]] = relationship(back_populates="datacenter", cascade="all, delete-orphan")
    ip_prefixes: Mapped[list["IpPrefix"]] = relationship(back_populates="datacenter", cascade="all, delete-orphan")


class Rack(Base):
    __tablename__ = "racks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64))
    row: Mapped[str | None] = mapped_column(String(32))
    capacity_u: Mapped[int] = mapped_column(Integer, default=42)

    datacenter: Mapped["DataCenter"] = relationship(back_populates="racks")
    devices: Mapped[list["Device"]] = relationship(back_populates="rack")
    servers: Mapped[list["Server"]] = relationship(back_populates="rack")
    storage_systems: Mapped[list["StorageSystem"]] = relationship(back_populates="rack")

    __table_args__ = (UniqueConstraint("datacenter_id", "name", name="uq_rack_datacenter_name"),)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id", ondelete="CASCADE"))
    rack_id: Mapped[int | None] = mapped_column(ForeignKey("racks.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(128))
    hostname: Mapped[str] = mapped_column(String(255))
    ip_address: Mapped[str] = mapped_column(String(45), index=True)
    vendor: Mapped[VendorType] = mapped_column(Enum(VendorType))
    device_type: Mapped[DeviceType] = mapped_column(Enum(DeviceType), default=DeviceType.SWITCH)
    model: Mapped[str | None] = mapped_column(String(128))
    serial_number: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[DeviceStatus] = mapped_column(Enum(DeviceStatus), default=DeviceStatus.UNKNOWN)
    position_u: Mapped[int | None] = mapped_column(Integer)
    height_u: Mapped[int] = mapped_column(Integer, default=1)
    tags: Mapped[dict | None] = mapped_column(JSONB)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    datacenter: Mapped["DataCenter"] = relationship(back_populates="devices")
    rack: Mapped["Rack | None"] = relationship(back_populates="devices")
    credentials: Mapped[list["DeviceCredential"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["DeviceMetric"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="device")
    sensors: Mapped[list["Sensor"]] = relationship(
        back_populates="device",
        foreign_keys="Sensor.device_id",
        cascade="all, delete-orphan",
    )
    config_backups: Mapped[list["DeviceConfigBackup"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class DeviceCredential(Base):
    __tablename__ = "device_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    protocol: Mapped[ProtocolType] = mapped_column(Enum(ProtocolType))
    username: Mapped[str | None] = mapped_column(String(128))
    password: Mapped[str | None] = mapped_column(String(512))
    community: Mapped[str | None] = mapped_column(String(128))
    api_token: Mapped[str | None] = mapped_column(String(512))
    port: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict | None] = mapped_column(JSONB)

    device: Mapped["Device"] = relationship(back_populates="credentials")


class DeviceMetric(Base):
    __tablename__ = "device_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    metric_name: Mapped[str] = mapped_column(String(128), index=True)
    metric_value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    device: Mapped["Device"] = relationship(back_populates="metrics")


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id", ondelete="CASCADE"))
    rack_id: Mapped[int | None] = mapped_column(ForeignKey("racks.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(128))
    hostname: Mapped[str] = mapped_column(String(255))
    ip_address: Mapped[str] = mapped_column(String(45), index=True)
    os_type: Mapped[ServerOSType] = mapped_column(Enum(ServerOSType))
    server_role: Mapped[ServerRole] = mapped_column(Enum(ServerRole), default=ServerRole.OTHER)
    cpu_cores: Mapped[int | None] = mapped_column(Integer)
    ram_gb: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[DeviceStatus] = mapped_column(Enum(DeviceStatus), default=DeviceStatus.UNKNOWN)
    position_u: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    datacenter: Mapped["DataCenter"] = relationship(back_populates="servers")
    rack: Mapped["Rack | None"] = relationship(back_populates="servers")
    credentials: Mapped[list["ServerCredential"]] = relationship(
        back_populates="server", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["ServerMetric"]] = relationship(back_populates="server", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="server")
    sensors: Mapped[list["Sensor"]] = relationship(
        back_populates="server",
        foreign_keys="Sensor.server_id",
        cascade="all, delete-orphan",
    )


class ServerCredential(Base):
    __tablename__ = "server_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"))
    protocol: Mapped[ProtocolType] = mapped_column(Enum(ProtocolType))
    username: Mapped[str | None] = mapped_column(String(128))
    password: Mapped[str | None] = mapped_column(String(512))
    community: Mapped[str | None] = mapped_column(String(128))
    api_token: Mapped[str | None] = mapped_column(String(512))
    port: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict | None] = mapped_column(JSONB)

    server: Mapped["Server"] = relationship(back_populates="credentials")


class ServerMetric(Base):
    __tablename__ = "server_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    metric_name: Mapped[str] = mapped_column(String(128), index=True)
    metric_value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    server: Mapped["Server"] = relationship(back_populates="metrics")


class StorageSystem(Base):
    __tablename__ = "storage_systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id", ondelete="CASCADE"))
    rack_id: Mapped[int | None] = mapped_column(ForeignKey("racks.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(128))
    hostname: Mapped[str] = mapped_column(String(255))
    ip_address: Mapped[str] = mapped_column(String(45), index=True)
    vendor: Mapped[StorageVendor] = mapped_column(Enum(StorageVendor, values_callable=_enum_values))
    model: Mapped[str | None] = mapped_column(String(128))
    storage_type: Mapped[StorageType] = mapped_column(Enum(StorageType, values_callable=_enum_values), default=StorageType.OTHER)
    total_capacity_tb: Mapped[float | None] = mapped_column(Float)
    used_capacity_tb: Mapped[float | None] = mapped_column(Float)
    status: Mapped[DeviceStatus] = mapped_column(Enum(DeviceStatus), default=DeviceStatus.UNKNOWN)
    position_u: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    datacenter: Mapped["DataCenter"] = relationship(back_populates="storage_systems")
    rack: Mapped["Rack | None"] = relationship(back_populates="storage_systems")
    credentials: Mapped[list["StorageCredential"]] = relationship(
        back_populates="storage", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["StorageMetric"]] = relationship(back_populates="storage", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="storage")
    sensors: Mapped[list["Sensor"]] = relationship(
        back_populates="storage",
        foreign_keys="Sensor.storage_id",
        cascade="all, delete-orphan",
    )


class StorageCredential(Base):
    __tablename__ = "storage_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    storage_id: Mapped[int] = mapped_column(ForeignKey("storage_systems.id", ondelete="CASCADE"))
    protocol: Mapped[ProtocolType] = mapped_column(Enum(ProtocolType))
    username: Mapped[str | None] = mapped_column(String(128))
    password: Mapped[str | None] = mapped_column(String(512))
    community: Mapped[str | None] = mapped_column(String(128))
    api_token: Mapped[str | None] = mapped_column(String(512))
    port: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict | None] = mapped_column(JSONB)

    storage: Mapped["StorageSystem"] = relationship(back_populates="credentials")


class StorageMetric(Base):
    __tablename__ = "storage_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    storage_id: Mapped[int] = mapped_column(ForeignKey("storage_systems.id", ondelete="CASCADE"), index=True)
    metric_name: Mapped[str] = mapped_column(String(128), index=True)
    metric_value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    storage: Mapped["StorageSystem"] = relationship(back_populates="metrics")


class NetworkMap(Base):
    __tablename__ = "network_maps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    topology: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    datacenter: Mapped["DataCenter"] = relationship(back_populates="network_maps")


class Sensor(Base):
    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    server_id: Mapped[int | None] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    storage_id: Mapped[int | None] = mapped_column(ForeignKey("storage_systems.id", ondelete="CASCADE"), index=True)
    asset_type: Mapped[SensorAssetType] = mapped_column(Enum(SensorAssetType))
    name: Mapped[str] = mapped_column(String(128))
    metric_key: Mapped[str] = mapped_column(String(128), index=True)
    unit: Mapped[str | None] = mapped_column(String(32))
    warning_limit: Mapped[float | None] = mapped_column(Float)
    error_limit: Mapped[float | None] = mapped_column(Float)
    higher_is_worse: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_value: Mapped[float | None] = mapped_column(Float)
    last_status: Mapped[SensorStatus] = mapped_column(Enum(SensorStatus), default=SensorStatus.UNKNOWN)
    last_message: Mapped[str | None] = mapped_column(String(255))
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device: Mapped["Device | None"] = relationship(back_populates="sensors", foreign_keys=[device_id])
    server: Mapped["Server | None"] = relationship(back_populates="sensors", foreign_keys=[server_id])
    storage: Mapped["StorageSystem | None"] = relationship(back_populates="sensors", foreign_keys=[storage_id])
    alerts: Mapped[list["Alert"]] = relationship(back_populates="sensor")

    __table_args__ = (
        UniqueConstraint("device_id", "metric_key", name="uq_sensor_device_metric"),
        UniqueConstraint("server_id", "metric_key", name="uq_sensor_server_metric"),
        UniqueConstraint("storage_id", "metric_key", name="uq_sensor_storage_metric"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    server_id: Mapped[int | None] = mapped_column(ForeignKey("servers.id", ondelete="SET NULL"))
    storage_id: Mapped[int | None] = mapped_column(ForeignKey("storage_systems.id", ondelete="SET NULL"))
    sensor_id: Mapped[int | None] = mapped_column(ForeignKey("sensors.id", ondelete="SET NULL"), index=True)
    datacenter_id: Mapped[int | None] = mapped_column(ForeignKey("datacenters.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity))
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.OPEN)
    source: Mapped[str] = mapped_column(String(64), default="system")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    device: Mapped["Device | None"] = relationship(back_populates="alerts")
    server: Mapped["Server | None"] = relationship(back_populates="alerts")
    storage: Mapped["StorageSystem | None"] = relationship(back_populates="alerts")
    sensor: Mapped["Sensor | None"] = relationship(back_populates="alerts")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(128))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IpAddressStatus(str, enum.Enum):
    FREE = "free"
    RESERVED = "reserved"
    ASSIGNED = "assigned"
    DHCP = "dhcp"


class IntegrationType(str, enum.Enum):
    PRTG = "prtg"
    VMWARE = "vmware"


class IpPrefix(Base):
    __tablename__ = "ip_prefixes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id", ondelete="CASCADE"), index=True)
    cidr: Mapped[str] = mapped_column(String(64), index=True)
    vlan: Mapped[int | None] = mapped_column(Integer)
    gateway: Mapped[str | None] = mapped_column(String(45))
    description: Mapped[str | None] = mapped_column(String(255))
    dns_servers: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    datacenter: Mapped["DataCenter"] = relationship(back_populates="ip_prefixes")
    addresses: Mapped[list["IpAddress"]] = relationship(back_populates="prefix", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("datacenter_id", "cidr", name="uq_ip_prefix_dc_cidr"),)


class IpAddress(Base):
    __tablename__ = "ip_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prefix_id: Mapped[int] = mapped_column(ForeignKey("ip_prefixes.id", ondelete="CASCADE"), index=True)
    address: Mapped[str] = mapped_column(String(45), index=True)
    status: Mapped[IpAddressStatus] = mapped_column(Enum(IpAddressStatus), default=IpAddressStatus.FREE)
    hostname: Mapped[str | None] = mapped_column(String(255))
    asset_type: Mapped[str | None] = mapped_column(String(32))
    asset_id: Mapped[int | None] = mapped_column(Integer)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    prefix: Mapped["IpPrefix"] = relationship(back_populates="addresses")
    device: Mapped["Device | None"] = relationship()

    __table_args__ = (UniqueConstraint("prefix_id", "address", name="uq_ip_address_prefix_addr"),)


class DeviceConfigBackup(Base):
    __tablename__ = "device_config_backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    protocol: Mapped[ProtocolType] = mapped_column(Enum(ProtocolType))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    device: Mapped["Device"] = relationship(back_populates="config_backups")


class IntegrationEndpoint(Base):
    __tablename__ = "integration_endpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datacenter_id: Mapped[int | None] = mapped_column(ForeignKey("datacenters.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    integration_type: Mapped[IntegrationType] = mapped_column(Enum(IntegrationType))
    base_url: Mapped[str] = mapped_column(String(512))
    username: Mapped[str | None] = mapped_column(String(128))
    api_token: Mapped[str | None] = mapped_column(String(512))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    extra: Mapped[dict | None] = mapped_column(JSONB)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LinkType(str, enum.Enum):
    FIBER = "fiber"
    COPPER = "copper"
    WIRELESS = "wireless"
    BACKUP = "backup"
    LOGICAL = "logical"


class PortOperStatus(str, enum.Enum):
    UP = "up"
    DOWN = "down"
    ADMIN_DOWN = "admin_down"
    TESTING = "testing"


class FirewallAction(str, enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    REJECT = "reject"


class SwitchPort(Base):
    __tablename__ = "switch_ports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    port_index: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(255))
    oper_status: Mapped[PortOperStatus] = mapped_column(Enum(PortOperStatus), default=PortOperStatus.DOWN)
    admin_status: Mapped[str] = mapped_column(String(16), default="up")
    speed_mbps: Mapped[int | None] = mapped_column(Integer)
    duplex: Mapped[str | None] = mapped_column(String(16))
    vlan_mode: Mapped[str] = mapped_column(String(16), default="access")
    access_vlan: Mapped[int | None] = mapped_column(Integer)
    trunk_vlans: Mapped[list | None] = mapped_column(JSONB)
    connected_device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    connected_port_name: Mapped[str | None] = mapped_column(String(64))
    link_type: Mapped[LinkType | None] = mapped_column(Enum(LinkType))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    services: Mapped[list | None] = mapped_column(JSONB)
    settings: Mapped[dict | None] = mapped_column(JSONB)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device: Mapped["Device"] = relationship(foreign_keys=[device_id])
    connected_device: Mapped["Device | None"] = relationship(foreign_keys=[connected_device_id])

    __table_args__ = (UniqueConstraint("device_id", "name", name="uq_switch_port_device_name"),)


class DeviceVlan(Base):
    __tablename__ = "device_vlans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    vlan_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(128))
    subnet: Mapped[str | None] = mapped_column(String(64))
    gateway: Mapped[str | None] = mapped_column(String(45))
    status: Mapped[str] = mapped_column(String(16), default="active")
    description: Mapped[str | None] = mapped_column(String(255))
    port_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    datacenter: Mapped["DataCenter"] = relationship()
    device: Mapped["Device | None"] = relationship()

    __table_args__ = (
        UniqueConstraint("datacenter_id", "device_id", "vlan_id", name="uq_device_vlan_scope"),
    )


class NetworkLink(Base):
    __tablename__ = "network_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id", ondelete="CASCADE"), index=True)
    from_device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    from_port: Mapped[str] = mapped_column(String(64))
    to_device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    to_port: Mapped[str] = mapped_column(String(64))
    link_type: Mapped[LinkType] = mapped_column(Enum(LinkType), default=LinkType.COPPER)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    bandwidth_mbps: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="up")
    description: Mapped[str | None] = mapped_column(String(255))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    datacenter: Mapped["DataCenter"] = relationship()
    from_device: Mapped["Device"] = relationship(foreign_keys=[from_device_id])
    to_device: Mapped["Device"] = relationship(foreign_keys=[to_device_id])


class BranchSite(Base):
    __tablename__ = "branch_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    location: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(255))
    primary_device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    primary_port: Mapped[str | None] = mapped_column(String(64))
    primary_link_type: Mapped[LinkType] = mapped_column(Enum(LinkType), default=LinkType.FIBER)
    backup_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_link_type: Mapped[LinkType | None] = mapped_column(Enum(LinkType))
    backup_device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    backup_port: Mapped[str | None] = mapped_column(String(64))
    backup_wireless_ssid: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="active")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    datacenter: Mapped["DataCenter"] = relationship()
    primary_device: Mapped["Device | None"] = relationship(foreign_keys=[primary_device_id])
    backup_device: Mapped["Device | None"] = relationship(foreign_keys=[backup_device_id])


class FirewallRule(Base):
    __tablename__ = "firewall_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    action: Mapped[FirewallAction] = mapped_column(Enum(FirewallAction), default=FirewallAction.ALLOW)
    source: Mapped[str | None] = mapped_column(String(255))
    destination: Mapped[str | None] = mapped_column(String(255))
    service: Mapped[str | None] = mapped_column(String(128))
    protocol: Mapped[str | None] = mapped_column(String(16))
    port: Mapped[str | None] = mapped_column(String(64))
    zone_in: Mapped[str | None] = mapped_column(String(64))
    zone_out: Mapped[str | None] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device: Mapped["Device"] = relationship()


class ConfigTemplate(Base):
    __tablename__ = "config_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor: Mapped[VendorType] = mapped_column(Enum(VendorType))
    category: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    template_body: Mapped[str] = mapped_column(Text)
    variables: Mapped[list | None] = mapped_column(JSONB)
    tags: Mapped[list | None] = mapped_column(JSONB)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("vendor", "name", name="uq_config_template_vendor_name"),)
