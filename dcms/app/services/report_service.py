from datetime import datetime
from io import BytesIO

from jinja2 import Template
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertSeverity, AlertStatus, DataCenter, Device, DeviceMetric, DeviceStatus, Server, StorageSystem


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
    .online { color: #276749; }
    .offline { color: #c53030; }
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
    <li>تنبيهات مفتوحة: {{ summary.open_alerts }}</li>
  </ul>
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
    <tr><th>العنوان</th><th>الخطورة</th><th>الرسالة</th><th>التاريخ</th></tr>
    {% for a in alerts %}
    <tr>
      <td>{{ a.title }}</td>
      <td class="{{ a.severity.value }}">{{ a.severity.value }}</td>
      <td>{{ a.message }}</td>
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

    alerts_result = await db.execute(
        select(Alert).where(
            Alert.datacenter_id == datacenter_id,
            Alert.status == AlertStatus.OPEN,
        )
    )
    alerts = list(alerts_result.scalars().all())

    summary = {
        "total_devices": len(devices),
        "online": sum(1 for d in devices if d.status == DeviceStatus.ONLINE),
        "offline": sum(1 for d in devices if d.status == DeviceStatus.OFFLINE),
        "open_alerts": len(alerts),
    }

    html = Template(REPORT_TEMPLATE).render(
        title=f"تقرير مركز البيانات: {datacenter.name}",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        summary=summary,
        devices=devices,
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
    }
