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


class VendorType(str, enum.Enum):
    CISCO = "cisco"
    JUNIPER = "juniper"
    FORTINET = "fortinet"
    GENERIC = "generic"


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
    devices: Mapped[list["Device"]] = relationship(back_populates="datacenter")
    servers: Mapped[list["Server"]] = relationship(back_populates="datacenter")
    storage_systems: Mapped[list["StorageSystem"]] = relationship(back_populates="datacenter")
    network_maps: Mapped[list["NetworkMap"]] = relationship(back_populates="datacenter")


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
    vendor: Mapped[StorageVendor] = mapped_column(Enum(StorageVendor))
    storage_type: Mapped[StorageType] = mapped_column(Enum(StorageType), default=StorageType.OTHER)
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


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    server_id: Mapped[int | None] = mapped_column(ForeignKey("servers.id", ondelete="SET NULL"))
    storage_id: Mapped[int | None] = mapped_column(ForeignKey("storage_systems.id", ondelete="SET NULL"))
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


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(128))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
