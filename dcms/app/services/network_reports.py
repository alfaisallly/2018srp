"""Professional network inventory and topology reports."""

from datetime import datetime
from io import BytesIO

from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import BranchSite, DataCenter, Device, DeviceType, DeviceVlan, FirewallRule, NetworkLink, SwitchPort
from app.services.network_inventory import get_network_overview
from app.services.topology_builder import LINK_LABELS, build_port_topology

NETWORK_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <title>{{ title }}</title>
  <style>
    body { font-family: 'Segoe UI', Tahoma, sans-serif; margin: 40px; direction: rtl; color: #1e293b; }
    h1 { color: #1a365d; border-bottom: 3px solid #3b82f6; padding-bottom: 10px; }
    h2 { color: #334155; margin-top: 28px; }
    .summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 20px 0; }
    .stat { background: #f1f5f9; border-radius: 8px; padding: 16px; text-align: center; }
    .stat strong { display: block; font-size: 28px; color: #3b82f6; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { border: 1px solid #cbd5e0; padding: 8px 10px; text-align: right; }
    th { background: #edf2f7; font-weight: 600; }
    .up { color: #16a34a; }
    .down { color: #dc2626; }
    .fiber { color: #0891b2; }
    .wireless { color: #9333ea; }
    .backup { color: #d97706; }
    .footer { margin-top: 40px; color: #64748b; font-size: 12px; }
  </style>
</head>
<body>
  <h1>{{ title }}</h1>
  <p>تاريخ التقرير: {{ generated_at }}</p>

  <div class="summary">
    <div class="stat"><strong>{{ overview.ports_total }}</strong>إجمالي المنافذ</div>
    <div class="stat"><strong class="up">{{ overview.ports_up }}</strong>منافذ نشطة</div>
    <div class="stat"><strong>{{ overview.vlans_total }}</strong>VLANs</div>
    <div class="stat"><strong>{{ overview.links_total }}</strong>روابط</div>
    <div class="stat"><strong>{{ overview.firewall_rules_total }}</strong>قواعد Firewall</div>
    <div class="stat"><strong>{{ overview.branch_sites_total }}</strong>مواقع فرعية</div>
  </div>

  <h2>السويجات والأجهزة</h2>
  <table>
    <tr><th>الجهاز</th><th>IP</th><th>النوع</th><th>المورّد</th><th>المنافذ</th><th>نشط</th></tr>
    {% for d in devices %}
    <tr>
      <td>{{ d.name }}</td>
      <td>{{ d.ip_address }}</td>
      <td>{{ d.device_type }}</td>
      <td>{{ d.vendor }}</td>
      <td>{{ d.port_total }}</td>
      <td class="up">{{ d.port_up }}</td>
    </tr>
    {% endfor %}
  </table>

  <h2>VLANs</h2>
  <table>
    <tr><th>ID</th><th>الاسم</th><th>الجهاز</th><th>الشبكة</th><th>Gateway</th><th>الحالة</th></tr>
    {% for v in vlans %}
    <tr>
      <td>{{ v.vlan_id }}</td>
      <td>{{ v.name }}</td>
      <td>{{ v.device_name or '—' }}</td>
      <td>{{ v.subnet or '—' }}</td>
      <td>{{ v.gateway or '—' }}</td>
      <td>{{ v.status }}</td>
    </tr>
    {% endfor %}
  </table>

  <h2>المنافذ والربط</h2>
  <table>
    <tr><th>الجهاز</th><th>المنفذ</th><th>الحالة</th><th>VLAN</th><th>السرعة</th><th>الربط</th><th>الخدمات</th></tr>
    {% for p in ports %}
    <tr>
      <td>{{ p.device_name }}</td>
      <td>{{ p.name }}</td>
      <td class="{{ p.status }}">{{ p.status }}</td>
      <td>{{ p.vlan_info }}</td>
      <td>{{ p.speed }}</td>
      <td>{{ p.connection }}</td>
      <td>{{ p.services }}</td>
    </tr>
    {% endfor %}
  </table>

  <h2>الروابط بين الأجهزة</h2>
  <table>
    <tr><th>من</th><th>منفذ</th><th>إلى</th><th>منفذ</th><th>النوع</th><th>العرض</th><th>الأولوية</th></tr>
    {% for l in links %}
    <tr>
      <td>{{ l.from_name }}</td>
      <td>{{ l.from_port }}</td>
      <td>{{ l.to_name }}</td>
      <td>{{ l.to_port }}</td>
      <td class="{{ l.link_class }}">{{ l.link_type }}</td>
      <td>{{ l.bandwidth }}</td>
      <td>{{ l.priority }}</td>
    </tr>
    {% endfor %}
  </table>

  <h2>المواقع الفرعية والخدمات البديلة</h2>
  <table>
    <tr><th>الموقع</th><th>الموقع الجغرافي</th><th>الرابط الأساسي</th><th>الخدمة البديلة</th><th>الحالة</th></tr>
    {% for b in branches %}
    <tr>
      <td>{{ b.name }}</td>
      <td>{{ b.location or '—' }}</td>
      <td>{{ b.primary }}</td>
      <td>{{ b.backup }}</td>
      <td>{{ b.status }}</td>
    </tr>
    {% endfor %}
  </table>

  <h2>قواعد Firewall</h2>
  <table>
    <tr><th>الجهاز</th><th>القاعدة</th><th>الإجراء</th><th>المصدر</th><th>الوجهة</th><th>الخدمة</th><th>المناطق</th></tr>
    {% for r in firewall_rules %}
    <tr>
      <td>{{ r.device_name }}</td>
      <td>{{ r.name }}</td>
      <td>{{ r.action }}</td>
      <td>{{ r.source or '—' }}</td>
      <td>{{ r.destination or '—' }}</td>
      <td>{{ r.service or '—' }}</td>
      <td>{{ r.zones }}</td>
    </tr>
    {% endfor %}
  </table>

  <div class="footer">تم إنشاء التقرير بواسطة DCMS — نظام إدارة الشبكة</div>
</body>
</html>
"""


async def generate_network_report(session: AsyncSession, datacenter_id: int) -> bytes:
    dc_result = await session.execute(select(DataCenter).where(DataCenter.id == datacenter_id))
    dc = dc_result.scalar_one_or_none()
    if not dc:
        raise ValueError("Datacenter not found")

    overview = await get_network_overview(session, datacenter_id)

    devices_result = await session.execute(
        select(Device).where(Device.datacenter_id == datacenter_id).order_by(Device.name)
    )
    devices = list(devices_result.scalars().all())

    device_rows = []
    for d in devices:
        ports_result = await session.execute(select(SwitchPort).where(SwitchPort.device_id == d.id))
        ports = list(ports_result.scalars().all())
        device_rows.append({
            "name": d.name,
            "ip_address": d.ip_address,
            "device_type": d.device_type.value if d.device_type else "other",
            "vendor": d.vendor.value,
            "port_total": len(ports),
            "port_up": sum(1 for p in ports if p.oper_status.value == "up"),
        })

    vlans_result = await session.execute(
        select(DeviceVlan)
        .where(DeviceVlan.datacenter_id == datacenter_id)
        .options(selectinload(DeviceVlan.device))
        .order_by(DeviceVlan.vlan_id)
    )
    vlans = [
        {
            "vlan_id": v.vlan_id,
            "name": v.name,
            "device_name": v.device.name if v.device else None,
            "subnet": v.subnet,
            "gateway": v.gateway,
            "status": v.status,
        }
        for v in vlans_result.scalars().all()
    ]

    ports_result = await session.execute(
        select(SwitchPort)
        .join(Device, SwitchPort.device_id == Device.id)
        .where(Device.datacenter_id == datacenter_id)
        .options(selectinload(SwitchPort.device), selectinload(SwitchPort.connected_device))
        .order_by(Device.name, SwitchPort.port_index)
    )
    port_rows = []
    for p in ports_result.scalars().all():
        vlan_info = str(p.access_vlan) if p.vlan_mode == "access" else f"Trunk: {p.trunk_vlans or []}"
        conn = "—"
        if p.connected_device:
            conn = f"{p.connected_device.name}:{p.connected_port_name or '?'}"
            if p.link_type:
                conn += f" ({LINK_LABELS.get(p.link_type, p.link_type.value)})"
        port_rows.append({
            "device_name": p.device.name,
            "name": p.name,
            "status": p.oper_status.value,
            "vlan_info": vlan_info,
            "speed": f"{p.speed_mbps} Mbps" if p.speed_mbps else "—",
            "connection": conn,
            "services": ", ".join(p.services or []) or "—",
        })

    links_result = await session.execute(
        select(NetworkLink)
        .where(NetworkLink.datacenter_id == datacenter_id)
        .options(selectinload(NetworkLink.from_device), selectinload(NetworkLink.to_device))
    )
    link_rows = []
    for l in links_result.scalars().all():
        link_rows.append({
            "from_name": l.from_device.name,
            "from_port": l.from_port,
            "to_name": l.to_device.name,
            "to_port": l.to_port,
            "link_type": LINK_LABELS.get(l.link_type, l.link_type.value),
            "link_class": l.link_type.value,
            "bandwidth": f"{l.bandwidth_mbps} Mbps" if l.bandwidth_mbps else "—",
            "priority": "أساسي" if l.is_primary else "احتياطي",
        })

    branches_result = await session.execute(
        select(BranchSite)
        .where(BranchSite.datacenter_id == datacenter_id)
        .options(selectinload(BranchSite.primary_device), selectinload(BranchSite.backup_device))
    )
    branch_rows = []
    for b in branches_result.scalars().all():
        primary = "—"
        if b.primary_device:
            primary = f"{b.primary_device.name}:{b.primary_port or '?'} ({LINK_LABELS.get(b.primary_link_type, '')})"
        backup = "—"
        if b.backup_enabled:
            backup_type = LINK_LABELS.get(b.backup_link_type, "لاسلكي") if b.backup_link_type else "لاسلكي"
            if b.backup_device:
                backup = f"{b.backup_device.name}:{b.backup_port or b.backup_wireless_ssid or '?'} ({backup_type})"
            else:
                backup = backup_type
        branch_rows.append({
            "name": b.name,
            "location": b.location,
            "primary": primary,
            "backup": backup,
            "status": b.status,
        })

    fw_result = await session.execute(
        select(FirewallRule)
        .join(Device)
        .where(Device.datacenter_id == datacenter_id)
        .options(selectinload(FirewallRule.device))
        .order_by(FirewallRule.order_index)
    )
    fw_rows = [
        {
            "device_name": r.device.name,
            "name": r.name,
            "action": r.action.value,
            "source": r.source,
            "destination": r.destination,
            "service": r.service,
            "zones": f"{r.zone_in or '?'} → {r.zone_out or '?'}",
        }
        for r in fw_result.scalars().all()
    ]

    html = Template(NETWORK_REPORT_TEMPLATE).render(
        title=f"تقرير الشبكة — {dc.name}",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        overview=overview,
        devices=device_rows,
        vlans=vlans,
        ports=port_rows,
        links=link_rows,
        branches=branch_rows,
        firewall_rules=fw_rows,
    )

    try:
        from weasyprint import HTML

        return HTML(string=html).write_pdf()
    except Exception:
        return html.encode("utf-8")
