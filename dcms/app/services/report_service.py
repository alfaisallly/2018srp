from datetime import datetime
from io import BytesIO

from jinja2 import Template
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertSeverity, AlertStatus, DataCenter, Device, DeviceStatus, Sensor, SensorStatus, Server, StorageSystem
from app.services.sensor_engine import SENSOR_STATUS_COLORS, get_sensor_summary


REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <title>{{ title }}</title>
  <style>
    body { font-family: 'Segoe UI', Tahoma, sans-serif; margin: 40px; direction: rtl; }
    h1 { color: #1a365d; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { border: 1px solid #cbd5e0; padding: 8px 12px; text-align: right; }
    th { background: #edf2f7; }
    .critical { color: #c53030; }
    .warning { color: #d69e2e; }
    .online, .up { color: #276749; }
    .offline, .down { color: #c53030; }
    .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-left: 6px; }
  </style>
</head>
<body>
  <h1>{{ title }}</h1>
  <p>تاريخ التقرير: {{ generated_at }}</p>
  <h2>ملخص</h2>
  <ul>
    <li>إجمالي الأجهزة: {{ summary.total_devices }}</li>
    <li>متصل: {{ summary.online }}</li>
    <li>غير متصل: {{ summary.offline }}</li>
    <li>السيرفرات: {{ summary.total_servers }} ({{ summary.online_servers }} متصل)</li>
    <li>التخزين: {{ summary.total_storage }} ({{ summary.online_storage }} متصل)</li>
    <li>الحساسات: {{ summary.total_sensors }} — <span class="up">{{ summary.sensors_up }} طبيعي</span>، <span class="warning">{{ summary.sensors_warning }} تحذير</span>، <span class="down">{{ summary.sensors_down }} تعطل</span></li>
    <li>تنبيهات مفتوحة: {{ summary.open_alerts }}</li>
  </ul>
  <h2>حالة الحساسات (PRTG)</h2>
  <table>
    <tr><th>الحالة</th><th>الأصل</th><th>الحساس</th><th>القيمة</th><th>الحدود</th><th>آخر فحص</th></tr>
    {% for s in sensors %}
    <tr>
      <td><span class="dot" style="background:{{ s.color }}"></span>{{ s.status_label }}</td>
      <td>{{ s.asset_name }}</td>
      <td>{{ s.name }}</td>
      <td>{{ s.value }}</td>
      <td>{{ s.limits }}</td>
      <td>{{ s.last_check or '—' }}</td>
    </tr>
    {% endfor %}
  </table>
  <h2>الأجهزة</h2>
  <table>
    <tr><th>الاسم</th><th>IP</th><th>المورّد</th><th>الحالة</th><th>آخر ظهور</th></tr>
    {% for d in devices %}
    <tr>
      <td>{{ d.name }}</td>
      <td>{{ d.ip_address }}</td>
      <td>{{ d.vendor.value }}</td>
      <td class="{{ d.status.value }}">{{ d.status.value }}</td>
      <td>{{ d.last_seen or '—' }}</td>
    </tr>
    {% endfor %}
  </table>
  <h2>التنبيهات المفتوحة</h2>
  <table>
    <tr><th>العنوان</th><th>الخطورة</th><th>الرسالة</th><th>المصدر</th><th>التاريخ</th></tr>
    {% for a in alerts %}
    <tr>
      <td>{{ a.title }}</td>
      <td class="{{ a.severity.value }}">{{ a.severity.value }}</td>
      <td>{{ a.message }}</td>
      <td>{{ a.source }}</td>
      <td>{{ a.created_at }}</td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
"""


async def generate_datacenter_report(db: AsyncSession, datacenter_id: int) -> bytes:
    dc_result = await db.execute(select(DataCenter).where(DataCenter.id == datacenter_id))
    datacenter = dc_result.scalar_one_or_none()
    if not datacenter:
        raise ValueError("Data center not found")

    devices_result = await db.execute(select(Device).where(Device.datacenter_id == datacenter_id))
    devices = list(devices_result.scalars().all())

    servers_result = await db.execute(select(Server).where(Server.datacenter_id == datacenter_id))
    servers = list(servers_result.scalars().all())

    storage_result = await db.execute(select(StorageSystem).where(StorageSystem.datacenter_id == datacenter_id))
    storage_items = list(storage_result.scalars().all())

    sensors_result = await db.execute(select(Sensor).where(Sensor.datacenter_id == datacenter_id).order_by(Sensor.name))
    sensors_raw = list(sensors_result.scalars().all())

    asset_names: dict[tuple[str, int], str] = {}
    for d in devices:
        asset_names[("device", d.id)] = d.name
    for s in servers:
        asset_names[("server", s.id)] = s.name
    for st in storage_items:
        asset_names[("storage", st.id)] = st.name

    sensors = []
    for s in sensors_raw:
        aid = s.device_id or s.server_id or s.storage_id or 0
        limits = []
        if s.warning_limit is not None:
            limits.append(f"تحذير {s.warning_limit}")
        if s.error_limit is not None:
            limits.append(f"خطأ {s.error_limit}")
        sensors.append(
            {
                "asset_name": asset_names.get((s.asset_type.value, aid), "—"),
                "name": s.name,
                "value": f"{s.last_value}{s.unit or ''}" if s.last_value is not None else "—",
                "limits": " / ".join(limits) if limits else "—",
                "status_label": s.last_status.value,
                "color": SENSOR_STATUS_COLORS.get(s.last_status, "#64748b"),
                "last_check": s.last_check_at.strftime("%Y-%m-%d %H:%M") if s.last_check_at else None,
            }
        )

    alerts_result = await db.execute(
        select(Alert).where(
            Alert.datacenter_id == datacenter_id,
            Alert.status == AlertStatus.OPEN,
        )
    )
    alerts = list(alerts_result.scalars().all())

    sensor_summary = await get_sensor_summary(db, datacenter_id)

    summary = {
        "total_devices": len(devices),
        "online": sum(1 for d in devices if d.status == DeviceStatus.ONLINE),
        "offline": sum(1 for d in devices if d.status == DeviceStatus.OFFLINE),
        "total_servers": len(servers),
        "online_servers": sum(1 for s in servers if s.status == DeviceStatus.ONLINE),
        "total_storage": len(storage_items),
        "online_storage": sum(1 for st in storage_items if st.status == DeviceStatus.ONLINE),
        "total_sensors": sensor_summary.get("total", 0),
        "sensors_up": sensor_summary.get("up", 0),
        "sensors_warning": sensor_summary.get("warning", 0),
        "sensors_down": sensor_summary.get("down", 0),
        "open_alerts": len(alerts),
    }

    html = Template(REPORT_TEMPLATE).render(
        title=f"تقرير مركز البيانات: {datacenter.name}",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        summary=summary,
        devices=devices,
        sensors=sensors,
        alerts=alerts,
    )

    try:
        from weasyprint import HTML

        return HTML(string=html).write_pdf()
    except Exception:
        return html.encode("utf-8")


async def get_dashboard_stats(db: AsyncSession) -> dict:
    total_devices = await db.scalar(select(func.count(Device.id))) or 0
    online = await db.scalar(
        select(func.count(Device.id)).where(Device.status == DeviceStatus.ONLINE)
    ) or 0
    open_alerts = await db.scalar(
        select(func.count(Alert.id)).where(Alert.status == AlertStatus.OPEN)
    ) or 0
    critical_alerts = await db.scalar(
        select(func.count(Alert.id)).where(
            Alert.status == AlertStatus.OPEN,
            Alert.severity == AlertSeverity.CRITICAL,
        )
    ) or 0
    datacenters = await db.scalar(select(func.count(DataCenter.id))) or 0
    total_servers = await db.scalar(select(func.count(Server.id))) or 0
    online_servers = await db.scalar(
        select(func.count(Server.id)).where(Server.status == DeviceStatus.ONLINE)
    ) or 0
    total_storage = await db.scalar(select(func.count(StorageSystem.id))) or 0
    online_storage = await db.scalar(
        select(func.count(StorageSystem.id)).where(StorageSystem.status == DeviceStatus.ONLINE)
    ) or 0

    sensor_summary = await get_sensor_summary(db)

    return {
        "datacenters": datacenters,
        "total_devices": total_devices,
        "online_devices": online,
        "offline_devices": total_devices - online,
        "total_servers": total_servers,
        "online_servers": online_servers,
        "total_storage": total_storage,
        "online_storage": online_storage,
        "open_alerts": open_alerts,
        "critical_alerts": critical_alerts,
        "total_sensors": sensor_summary.get("total", 0),
        "sensors_up": sensor_summary.get("up", 0),
        "sensors_warning": sensor_summary.get("warning", 0),
        "sensors_down": sensor_summary.get("down", 0),
    }
