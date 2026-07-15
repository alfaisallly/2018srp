const API = '/api/v1';
let token = localStorage.getItem('dcms_token');
let network = null;
let dcNetwork = null;
let currentUser = null;
let currentPermissions = new Set();
let currentDcOverview = null;
let selectedDatacenterId = null;

const ROLE_LABELS = {
  admin: 'مدير النظام',
  editor: 'قراءة وتعديل',
  operator: 'مشغّل',
  viewer: 'قراءة فقط',
  custom: 'مخصص',
};

const vendorColors = { cisco: '#049fd9', juniper: '#84bd00', fortinet: '#ee3124', generic: '#94a3b8' };
const statusColors = { online: '#22c55e', offline: '#ef4444', degraded: '#eab308', unknown: '#64748b' };

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }
  const res = await fetch(`${API}${path}`, { ...options, headers });
  if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return null;
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('json')) return res.json();
  return res.blob();
}

function hasPerm(perm) {
  return currentPermissions.has(perm);
}

function applyPermissionsUI() {
  document.querySelectorAll('[data-perm]').forEach(el => {
    const perm = el.dataset.perm;
    const allowed = hasPerm(perm);
    el.classList.toggle('hidden', !allowed);
  });
  const canManage = (p) => hasPerm(p);
  document.getElementById('show-add-device')?.classList.toggle('hidden', !canManage('manage_devices'));
  document.getElementById('show-discover')?.classList.toggle('hidden', !canManage('manage_devices'));
  document.getElementById('poll-all-devices')?.classList.toggle('hidden', !canManage('manage_devices'));
  document.getElementById('show-add-server')?.classList.toggle('hidden', !canManage('manage_servers'));
  document.getElementById('poll-all-servers')?.classList.toggle('hidden', !canManage('manage_servers'));
  document.getElementById('show-add-storage')?.classList.toggle('hidden', !canManage('manage_storage'));
  document.getElementById('poll-all-storage')?.classList.toggle('hidden', !canManage('manage_storage'));
  document.getElementById('download-report')?.classList.toggle('hidden', !hasPerm('view_reports'));
  document.getElementById('seed-sensors')?.classList.toggle('hidden', !canManage('manage_devices'));
  document.getElementById('show-add-dc')?.classList.toggle('hidden', !hasPerm('manage_datacenters'));
}

function logout() {
  token = null;
  currentUser = null;
  currentPermissions = new Set();
  localStorage.removeItem('dcms_token');
  document.getElementById('logout-btn')?.classList.add('hidden');
  showPanel('login');
}

function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.add('hidden'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  if (name === 'login') {
    document.getElementById('login-panel').classList.remove('hidden');
    document.querySelector('nav').style.display = 'none';
    document.getElementById('logout-btn')?.classList.add('hidden');
    return;
  }
  document.querySelector('nav').style.display = 'flex';
  document.getElementById('logout-btn')?.classList.remove('hidden');
  document.getElementById(`${name}-panel`).classList.remove('hidden');
  document.querySelector(`[data-panel="${name}"]`)?.classList.add('active');
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData();
  form.append('username', document.getElementById('username').value);
  form.append('password', document.getElementById('password').value);
  try {
    const res = await fetch(`${API}/auth/login`, { method: 'POST', body: form });
    if (!res.ok) throw new Error('بيانات الدخول غير صحيحة');
    const data = await res.json();
    token = data.access_token;
    localStorage.setItem('dcms_token', token);
    document.getElementById('login-error').textContent = '';
    await initApp();
  } catch (err) {
    document.getElementById('login-error').textContent = err.message;
  }
});

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const panel = btn.dataset.panel;
    showPanel(panel);
    if (panel === 'devices') loadDevices();
    if (panel === 'servers') loadServers();
    if (panel === 'storage') loadStorage();
    if (panel === 'network-map') loadNetworkMap();
    if (panel === 'sensors') loadSensors();
    if (panel === 'alerts') loadAlerts();
    if (panel === 'reports') loadReportSelector();
    if (panel === 'users') loadUsers();
    if (panel === 'dashboard') loadDashboard();
    if (panel === 'import-excel') resetExcelImportUI();
  });
});

document.getElementById('logout-btn')?.addEventListener('click', () => {
  if (confirm('هل تريد تسجيل الخروج؟')) logout();
});

async function initApp() {
  const user = await api('/auth/me');
  currentUser = user;
  currentPermissions = new Set(user.permission_keys || []);
  document.getElementById('user-info').textContent = `${user.full_name || user.username} (${ROLE_LABELS[user.role] || user.role})`;
  applyPermissionsUI();
  showPanel('dashboard');
  await loadDashboard();
}

async function loadDashboard() {
  document.getElementById('dc-detail-view').classList.add('hidden');
  selectedDatacenterId = null;
  currentDcOverview = null;
  document.getElementById('dc-list-view').classList.remove('hidden');

  const stats = await api('/reports/dashboard');
  document.getElementById('stats-grid').innerHTML = `
    <div class="stat-card"><div class="value">${stats.datacenters}</div><div class="label">مراكز البيانات</div></div>
    <div class="stat-card"><div class="value">${stats.total_devices}</div><div class="label">أجهزة الشبكة</div></div>
    <div class="stat-card"><div class="value">${stats.total_servers || 0}</div><div class="label">السيرفرات</div></div>
    <div class="stat-card"><div class="value">${stats.total_storage || 0}</div><div class="label">التخزين</div></div>
    <div class="stat-card"><div class="value status-online">${stats.online_devices}</div><div class="label">شبكة متصلة</div></div>
    <div class="stat-card"><div class="value">${stats.open_alerts}</div><div class="label">تنبيهات مفتوحة</div></div>
    <div class="stat-card"><div class="value">${stats.total_sensors || 0}</div><div class="label">الحساسات</div></div>
  `;

  const dcs = await api('/datacenters');
  if (!dcs.length) {
    document.getElementById('datacenters-grid').innerHTML =
      '<p style="color:var(--muted);grid-column:1/-1">لا توجد مراكز بيانات — أضف مركزاً للبدء</p>';
    return;
  }

  const overviews = (await Promise.all(
    dcs.map(d => api(`/datacenters/${d.id}/overview`).catch(() => null))
  )).filter(Boolean);

  document.getElementById('datacenters-grid').innerHTML = overviews.map(ov => {
    const d = ov.datacenter;
    const s = ov.summary || {};
    return `<div class="dc-card" onclick="openDatacenterDetail(${d.id})">
      <h3>${d.name}</h3>
      <p class="dc-meta">${d.location || 'بدون موقع'}${d.description ? ' — ' + d.description : ''}</p>
      <div class="dc-chips">
        <span class="chip-sm">🔀 ${s.switches || 0} سويج</span>
        <span class="chip-sm">🛡️ ${s.firewalls || 0} جدار</span>
        <span class="chip-sm">🖥️ ${s.servers || 0} خادم</span>
        <span class="chip-sm">💾 ${s.storage || 0} تخزين</span>
        <span class="chip-sm">⚠️ ${s.open_alerts || 0} تنبيه</span>
      </div>
    </div>`;
  }).join('');
}

const DEVICE_TYPE_LABELS = { switch: 'سويج', firewall: 'جدار حماية', router: 'راوتر', other: 'أخرى' };
const VENDOR_LABELS = { cisco: 'Cisco', juniper: 'Juniper', fortinet: 'Fortinet', generic: 'Generic' };
const ASSET_TYPE_LABELS = { device: 'شبكة', server: 'سيرفر', storage: 'تخزين' };

function assetTableRows(items, type) {
  if (!items?.length) return `<tr><td colspan="6" style="text-align:center;color:var(--muted)">لا توجد أصول</td></tr>`;
  return items.map(a => {
    const extra = type === 'server'
      ? `<td>${a.os_type || '—'}</td><td>${a.server_role || '—'}</td>`
      : type === 'storage'
        ? `<td>${a.vendor || '—'}</td><td>${a.storage_type || '—'}</td>`
        : `<td>${VENDOR_LABELS[a.vendor] || a.vendor || '—'}</td><td>${DEVICE_TYPE_LABELS[a.device_type] || a.device_type || '—'}</td>`;
    return `<tr>
      <td>${a.name}</td><td>${a.ip_address}</td>${extra}
      <td class="status-${a.status}">${a.status}</td>
      <td>${a.last_seen ? new Date(a.last_seen).toLocaleString('ar') : '—'}</td>
    </tr>`;
  }).join('');
}

async function openDatacenterDetail(dcId) {
  selectedDatacenterId = dcId;
  currentDcOverview = await api(`/datacenters/${dcId}/overview`);
  document.getElementById('dc-list-view').classList.add('hidden');
  document.getElementById('dc-detail-view').classList.remove('hidden');
  const dc = currentDcOverview.datacenter;
  document.getElementById('dc-detail-name').textContent = dc.name;
  document.getElementById('dc-detail-location').textContent =
    [dc.location, dc.description, dc.contact_email].filter(Boolean).join(' — ') || 'بدون تفاصيل';

  const s = currentDcOverview.summary;
  document.getElementById('dc-detail-stats').innerHTML = `
    <div class="stat-card"><div class="value">${s.switches}</div><div class="label">سويجات</div></div>
    <div class="stat-card"><div class="value">${s.firewalls}</div><div class="label">جدران حماية</div></div>
    <div class="stat-card"><div class="value">${s.servers}</div><div class="label">خوادم</div></div>
    <div class="stat-card"><div class="value">${s.storage}</div><div class="label">تخزين</div></div>
    <div class="stat-card"><div class="value status-online">${s.online_devices + s.online_servers + s.online_storage}</div><div class="label">متصل</div></div>
    <div class="stat-card"><div class="value">${s.open_alerts}</div><div class="label">تنبيهات</div></div>
    <div class="stat-card"><div class="value sensor-status-up">${s.sensors_up}</div><div class="label">حساسات طبيعية</div></div>
    <div class="stat-card"><div class="value sensor-status-down">${s.sensors_down}</div><div class="label">حساسات متعطلة</div></div>
  `;

  document.querySelectorAll('.dc-tab').forEach(t => t.classList.toggle('active', t.dataset.dcTab === 'overview'));
  renderDcTab('overview');
}

function renderDcTab(tab) {
  if (!currentDcOverview) return;
  const el = document.getElementById('dc-tab-content');
  const s = currentDcOverview.summary;
  const dc = currentDcOverview.datacenter;

  if (tab === 'overview') {
    el.innerHTML = `
      <h3>نظرة عامة — ${dc.name}</h3>
      <div class="dc-overview-grid">
        <div class="dc-overview-card"><h4>🔀 السويجات (${s.switches})</h4><ul>${currentDcOverview.switches.slice(0,5).map(d=>`<li>${d.name} — ${d.ip_address}</li>`).join('') || '<li>لا يوجد</li>'}</ul></div>
        <div class="dc-overview-card"><h4>🛡️ جدران الحماية (${s.firewalls})</h4><ul>${currentDcOverview.firewalls.slice(0,5).map(d=>`<li>${d.name} — ${d.ip_address}</li>`).join('') || '<li>لا يوجد</li>'}</ul></div>
        <div class="dc-overview-card"><h4>🖥️ الخوادم (${s.servers})</h4><ul>${currentDcOverview.servers.slice(0,5).map(d=>`<li>${d.name} — ${d.ip_address}</li>`).join('') || '<li>لا يوجد</li>'}</ul></div>
        <div class="dc-overview-card"><h4>💾 التخزين (${s.storage})</h4><ul>${currentDcOverview.storage.slice(0,5).map(d=>`<li>${d.name} — ${d.ip_address}</li>`).join('') || '<li>لا يوجد</li>'}</ul></div>
        <div class="dc-overview-card"><h4>⚠️ تنبيهات (${s.open_alerts})</h4><ul>${currentDcOverview.alerts.slice(0,5).map(a=>`<li class="severity-${a.severity}">${a.title}</li>`).join('') || '<li>لا يوجد</li>'}</ul></div>
        <div class="dc-overview-card"><h4>📊 مخططات (${s.network_maps})</h4><ul>${currentDcOverview.network_maps.map(m=>`<li>${m.name}</li>`).join('') || '<li>لا يوجد — استورد Excel أو أنشئ مخططاً</li>'}</ul></div>
      </div>`;
    return;
  }

  if (tab === 'switches') {
    el.innerHTML = `<h3>السويجات</h3><table><thead><tr><th>الاسم</th><th>IP</th><th>المورّد</th><th>النوع</th><th>الحالة</th><th>آخر ظهور</th></tr></thead><tbody>${assetTableRows(currentDcOverview.switches, 'device')}</tbody></table>`;
    return;
  }

  if (tab === 'firewalls') {
    el.innerHTML = `<h3>جدران الحماية</h3><table><thead><tr><th>الاسم</th><th>IP</th><th>المورّد</th><th>النوع</th><th>الحالة</th><th>آخر ظهور</th></tr></thead><tbody>${assetTableRows(currentDcOverview.firewalls, 'device')}</tbody></table>`;
    return;
  }

  if (tab === 'servers') {
    el.innerHTML = `<h3>الخوادم</h3><table><thead><tr><th>الاسم</th><th>IP</th><th>نظام التشغيل</th><th>الدور</th><th>الحالة</th><th>آخر ظهور</th></tr></thead><tbody>${assetTableRows(currentDcOverview.servers, 'server')}</tbody></table>`;
    return;
  }

  if (tab === 'storage') {
    el.innerHTML = `<h3>أنظمة التخزين</h3><table><thead><tr><th>الاسم</th><th>IP</th><th>المورّد</th><th>النوع</th><th>الحالة</th><th>آخر ظهور</th></tr></thead><tbody>${assetTableRows(currentDcOverview.storage, 'storage')}</tbody></table>`;
    return;
  }

  if (tab === 'topology') {
    const maps = currentDcOverview.network_maps;
    if (!maps.length) {
      el.innerHTML = `<h3>مخطط الربط</h3><p class="muted">لا يوجد مخطط لهذا المركز. استورد ملف Excel مع ورقة Links أو أنشئ مخططاً من تبويب خريطة الشبكة.</p>`;
      return;
    }
    const map = maps[0];
    el.innerHTML = `<h3>مخطط الربط — ${map.name}</h3>
      ${maps.length > 1 ? `<p class="muted">يعرض: ${map.name} (${maps.length} مخططات متاحة)</p>` : ''}
      <div id="dc-topology-graph"></div>`;
    setTimeout(() => renderDcTopology(map.topology), 50);
    return;
  }

  if (tab === 'sensors') {
    const sensors = currentDcOverview.sensors;
    el.innerHTML = `<h3>الحساسات</h3><table><thead><tr><th></th><th>الحساس</th><th>النوع</th><th>القيمة</th><th>الحالة</th><th>آخر فحص</th></tr></thead><tbody>
      ${sensors.length ? sensors.map(s => `<tr>
        <td><span class="sensor-dot ${s.last_status}"></span></td>
        <td>${s.name}</td><td>${ASSET_TYPE_LABELS[s.asset_type] || s.asset_type}</td>
        <td>${s.last_value != null ? s.last_value + (s.unit || '') : '—'}</td>
        <td class="sensor-status-${s.last_status}">${s.status_label}</td>
        <td>${s.last_check_at ? new Date(s.last_check_at).toLocaleString('ar') : '—'}</td>
      </tr>`).join('') : '<tr><td colspan="6" style="text-align:center;color:var(--muted)">لا توجد حساسات — شغّل الفحص</td></tr>'}
    </tbody></table>`;
    return;
  }

  if (tab === 'alerts') {
    const alerts = currentDcOverview.alerts;
    el.innerHTML = `<h3>التنبيهات</h3><table><thead><tr><th>العنوان</th><th>الخطورة</th><th>الحالة</th><th>المصدر</th><th>التاريخ</th><th>إجراء</th></tr></thead><tbody>
      ${alerts.length ? alerts.map(a => `<tr>
        <td>${a.title}</td><td class="severity-${a.severity}">${a.severity}</td><td>${a.status}</td>
        <td>${a.source}</td><td>${new Date(a.created_at).toLocaleString('ar')}</td>
        <td>${a.status === 'open' && hasPerm('manage_alerts') ? `<button class="btn-sm" onclick="ackAlert(${a.id});openDatacenterDetail(${selectedDatacenterId})">اعتماد</button>` : '—'}</td>
      </tr>`).join('') : '<tr><td colspan="6" style="text-align:center;color:var(--muted)">لا توجد تنبيهات مفتوحة</td></tr>'}
    </tbody></table>`;
    return;
  }

  if (tab === 'reports') {
    el.innerHTML = `<h3>تقارير ${dc.name}</h3>
      <p>تصدير تقرير PDF/HTML يشمل السويجات وجدران الحماية والخوادم والتخزين والحساسات والتنبيهات.</p>
      <div class="form-actions">
        <button id="dc-download-report">تحميل تقرير المركز</button>
        <button class="btn-secondary" onclick="showPanel('reports')">فتح تبويب التقارير</button>
      </div>`;
    document.getElementById('dc-download-report')?.addEventListener('click', () => downloadDcReport(selectedDatacenterId));
  }
}

function renderDcTopology(topology) {
  const container = document.getElementById('dc-topology-graph');
  if (!container || !topology?.nodes?.length) return;
  if (dcNetwork) { dcNetwork.destroy(); dcNetwork = null; }
  const nodes = new vis.DataSet(topology.nodes.map(n => ({
    id: n.id, label: n.label || n.id, color: n.color || '#94a3b8', shape: n.shape || 'dot',
  })));
  const edges = new vis.DataSet((topology.edges || []).map((e, i) => ({
    id: i, from: e.from, to: e.to, label: e.label || '', arrows: 'to',
  })));
  dcNetwork = new vis.Network(container, { nodes, edges }, {
    physics: { stabilization: true },
    interaction: { hover: true },
    edges: { font: { color: '#94a3b8', size: 10 } },
  });
}

async function downloadDcReport(dcId) {
  const blob = await api(`/reports/datacenter/${dcId}/pdf`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `report-dc-${dcId}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

document.getElementById('back-to-dcs')?.addEventListener('click', loadDashboard);
document.getElementById('show-add-dc')?.addEventListener('click', () => {
  document.getElementById('add-dc-form').classList.toggle('hidden');
});
document.getElementById('cancel-add-dc')?.addEventListener('click', () => {
  document.getElementById('add-dc-form').classList.add('hidden');
});
document.getElementById('dc-create-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await api('/datacenters', {
      method: 'POST',
      body: {
        name: document.getElementById('dc-name').value,
        location: document.getElementById('dc-location').value || null,
        contact_email: document.getElementById('dc-email').value || null,
        description: document.getElementById('dc-desc').value || null,
      },
    });
    document.getElementById('add-dc-form').classList.add('hidden');
    document.getElementById('dc-create-form').reset();
    loadDashboard();
  } catch (err) { alert(err.message); }
});
document.querySelectorAll('.dc-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.dc-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    renderDcTab(btn.dataset.dcTab);
  });
});

async function loadDevices() {
  await populateDatacenterSelects();
  const devices = await api('/devices');
  const tbody = document.querySelector('#devices-table tbody');
  tbody.innerHTML = devices.map(d => `
    <tr>
      <td>${d.name}</td>
      <td>${d.ip_address}</td>
      <td>${d.vendor}</td>
      <td class="status-${d.status}">${d.status}</td>
      <td>${d.last_seen ? new Date(d.last_seen).toLocaleString('ar') : '—'}</td>
      <td><button class="btn-sm" onclick="pollDevice(${d.id})">فحص</button></td>
    </tr>
  `).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--muted)">لا توجد أجهزة</td></tr>';
}

async function populateDatacenterSelects() {
  const dcs = await api('/datacenters');
  ['dev-dc', 'disc-dc', 'srv-dc', 'sto-dc'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = dcs.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
  });
}

function toggleProtocolFields() {
  const protocol = document.getElementById('dev-protocol').value;
  document.getElementById('lbl-community').classList.toggle('hidden', protocol !== 'snmp');
  document.getElementById('lbl-username').classList.toggle('hidden', !['ssh', 'netconf'].includes(protocol));
  document.getElementById('lbl-password').classList.toggle('hidden', !['ssh', 'netconf'].includes(protocol));
  document.getElementById('lbl-token').classList.toggle('hidden', protocol !== 'rest');
}

document.getElementById('dev-vendor').addEventListener('change', () => {
  const v = document.getElementById('dev-vendor').value;
  const typeEl = document.getElementById('dev-type');
  if (v === 'fortinet') typeEl.value = 'firewall';
  else if (v === 'cisco' || v === 'juniper') typeEl.value = 'switch';
});

document.getElementById('dev-protocol').addEventListener('change', toggleProtocolFields);

document.getElementById('show-add-device').addEventListener('click', async () => {
  await populateDatacenterSelects();
  document.getElementById('discover-form').classList.add('hidden');
  document.getElementById('add-device-form').classList.toggle('hidden');
  toggleProtocolFields();
});

document.getElementById('cancel-add-device').addEventListener('click', () => {
  document.getElementById('add-device-form').classList.add('hidden');
});

document.getElementById('show-discover').addEventListener('click', async () => {
  await populateDatacenterSelects();
  document.getElementById('add-device-form').classList.add('hidden');
  document.getElementById('discover-form').classList.toggle('hidden');
});

document.getElementById('cancel-discover').addEventListener('click', () => {
  document.getElementById('discover-form').classList.add('hidden');
});

document.getElementById('device-create-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const protocol = document.getElementById('dev-protocol').value;
  const portVal = document.getElementById('dev-port').value;
  const cred = { protocol, port: portVal ? parseInt(portVal) : null };
  if (protocol === 'snmp') cred.community = document.getElementById('dev-community').value;
  if (['ssh', 'netconf'].includes(protocol)) {
    cred.username = document.getElementById('dev-username').value;
    cred.password = document.getElementById('dev-password').value;
  }
  if (protocol === 'rest') cred.api_token = document.getElementById('dev-token').value;

  const body = {
    datacenter_id: parseInt(document.getElementById('dev-dc').value),
    name: document.getElementById('dev-name').value,
    hostname: document.getElementById('dev-hostname').value,
    ip_address: document.getElementById('dev-ip').value,
    vendor: document.getElementById('dev-vendor').value,
    device_type: document.getElementById('dev-type').value,
    credentials: [cred],
  };

  try {
    const device = await api('/devices', { method: 'POST', body });
    document.getElementById('add-device-msg').textContent = '';
    document.getElementById('add-device-form').classList.add('hidden');
    await loadDevices();
    const poll = confirm('تمت الإضافة. هل تريد فحص الجهاز الآن؟');
    if (poll) await pollDevice(device.id);
  } catch (err) {
    document.getElementById('add-device-msg').textContent = err.message;
  }
});

document.getElementById('network-discover-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const statusEl = document.getElementById('discover-status');
  const resultsEl = document.getElementById('discover-results');
  statusEl.textContent = 'جاري المسح... قد يستغرق دقائق';
  resultsEl.innerHTML = '';

  const body = {
    datacenter_id: parseInt(document.getElementById('disc-dc').value),
    community: document.getElementById('disc-community').value,
    port: parseInt(document.getElementById('disc-port').value) || 161,
  };
  const cidr = document.getElementById('disc-cidr').value.trim();
  const start = document.getElementById('disc-start').value.trim();
  const end = document.getElementById('disc-end').value.trim();
  if (cidr) body.cidr = cidr;
  else if (start && end) { body.start_ip = start; body.end_ip = end; }
  else { statusEl.textContent = 'أدخل CIDR أو نطاق IP'; return; }

  try {
    const result = await api('/devices/discover', { method: 'POST', body });
    statusEl.textContent = `تم مسح ${result.scanned} IP — وُجد ${result.found} جهاز`;
    if (result.devices.length === 0) {
      resultsEl.innerHTML = '<p class="muted">لم يُكتشف أي جهاز. تحقق من Community والاتصال.</p>';
      return;
    }
    resultsEl.innerHTML = `
      <table class="discover-table">
        <thead><tr><th></th><th>IP</th><th>Hostname</th><th>المورّد</th><th>الوصف</th></tr></thead>
        <tbody>${result.devices.map(d => `
          <tr>
            <td><input type="checkbox" class="disc-check" data-ip="${d.ip_address}" checked></td>
            <td>${d.ip_address}</td>
            <td>${d.hostname}</td>
            <td>${d.vendor}</td>
            <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${d.sys_descr}</td>
          </tr>`).join('')}
        </tbody>
      </table>
      <div class="import-bar">
        <button id="import-selected">استيراد المحدد (${result.found})</button>
      </div>`;
    document.getElementById('import-selected').addEventListener('click', importSelectedDevices);
  } catch (err) {
    statusEl.textContent = `خطأ: ${err.message}`;
  }
});

async function importSelectedDevices() {
  const ips = [...document.querySelectorAll('.disc-check:checked')].map(c => c.dataset.ip);
  if (!ips.length) return alert('حدّد جهازاً واحداً على الأقل');
  const dcId = parseInt(document.getElementById('disc-dc').value);
  const community = document.getElementById('disc-community').value;
  const port = parseInt(document.getElementById('disc-port').value) || 161;
  try {
    const result = await api('/devices/import-discovered', {
      method: 'POST',
      body: { datacenter_id: dcId, community, port, ips, poll_after_import: true },
    });
    alert(`تم استيراد ${result.imported} جهاز (${result.skipped} تخطّى)`);
    document.getElementById('discover-form').classList.add('hidden');
    loadDevices();
  } catch (e) { alert(e.message); }
}

document.getElementById('poll-all-devices').addEventListener('click', async () => {
  try {
    const result = await api('/devices/poll-all', { method: 'POST' });
    alert(`فحص ${result.total}: ${result.online} متصل، ${result.offline} غير متصل`);
    loadDevices();
  } catch (e) { alert(e.message); }
});

async function pollDevice(id) {
  try {
    const result = await api(`/devices/${id}/poll`, { method: 'POST' });
    alert(result.success ? `متصل عبر ${result.protocol}` : `فشل: ${result.error}`);
    loadDevices();
  } catch (e) { alert(e.message); }
}

async function loadNetworkMap() {
  const maps = await api('/network-maps');
  const selector = document.getElementById('map-selector');
  selector.innerHTML = maps.map(m => `<option value="${m.id}">${m.name}</option>`).join('')
    || '<option value="">—</option>';

  if (maps.length === 0) {
    await buildAutoMap();
  } else {
    renderMap(maps[0]);
  }
  selector.onchange = async () => {
    const m = maps.find(x => x.id == selector.value);
    if (m) renderMap(m);
  };
}

async function buildAutoMap() {
  const [devices, dcs] = await Promise.all([api('/devices'), api('/datacenters')]);
  const nodes = [];
  const edges = [];

  dcs.forEach((dc, i) => {
    nodes.push({ id: `dc-${dc.id}`, label: dc.name, group: 'datacenter', shape: 'box', color: '#3b82f6' });
  });

  devices.forEach(d => {
    nodes.push({
      id: `dev-${d.id}`,
      label: `${d.name}\n${d.ip_address}`,
      group: d.vendor,
      color: { background: vendorColors[d.vendor] || vendorColors.generic, border: statusColors[d.status] },
      borderWidth: 2,
    });
    edges.push({ from: `dc-${d.datacenter_id}`, to: `dev-${d.id}`, arrows: 'to' });
  });

  renderTopology({ nodes, edges });
}

function renderMap(mapData) {
  const topo = mapData.topology;
  if (topo && topo.nodes && topo.nodes.length) {
    renderTopology(topo);
  } else {
    buildAutoMap();
  }
}

function renderTopology(topology) {
  const container = document.getElementById('network-graph');
  const data = {
    nodes: new vis.DataSet(topology.nodes),
    edges: new vis.DataSet(topology.edges || []),
  };
  const options = {
    layout: { improvedLayout: true },
    physics: { stabilization: { iterations: 150 } },
    nodes: { font: { color: '#f1f5f9', size: 13 }, shape: 'dot', size: 20 },
    edges: { color: { color: '#475569' }, smooth: { type: 'continuous' } },
    interaction: { hover: true, tooltipDelay: 200 },
  };
  if (network) network.destroy();
  network = new vis.Network(container, data, options);
}

document.getElementById('refresh-map').addEventListener('click', loadNetworkMap);
document.getElementById('refresh-devices').addEventListener('click', loadDevices);

async function loadAlerts() {
  const alerts = await api('/alerts');
  const tbody = document.querySelector('#alerts-table tbody');
  tbody.innerHTML = alerts.map(a => `
    <tr>
      <td>${a.title}</td>
      <td class="severity-${a.severity}">${a.severity}</td>
      <td>${a.status}</td>
      <td>${a.source || '—'}</td>
      <td>${new Date(a.created_at).toLocaleString('ar')}</td>
      <td>
        ${a.status === 'open' && hasPerm('manage_alerts') ? `<button class="btn-sm" onclick="ackAlert(${a.id})">اعتماد</button> ` : ''}
        ${a.status !== 'resolved' && hasPerm('manage_alerts') ? `<button class="btn-sm" onclick="resolveAlert(${a.id})">حل</button>` : '—'}
      </td>
    </tr>
  `).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--muted)">لا توجد تنبيهات</td></tr>';
}

async function ackAlert(id) {
  await api(`/alerts/${id}`, { method: 'PATCH', body: { status: 'acknowledged' } });
  loadAlerts();
}

async function resolveAlert(id) {
  await api(`/alerts/${id}`, { method: 'PATCH', body: { status: 'resolved' } });
  loadAlerts();
}

async function loadReportSelector() {
  const dcs = await api('/datacenters');
  document.getElementById('report-dc-selector').innerHTML = dcs.map(d =>
    `<option value="${d.id}">${d.name}</option>`
  ).join('');
}

document.getElementById('download-report').addEventListener('click', async () => {
  const dcId = document.getElementById('report-dc-selector').value;
  if (!dcId) return alert('اختر مركز بيانات');
  const blob = await api(`/reports/datacenter/${dcId}/pdf`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `report-dc-${dcId}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
});

// ─── Servers ───
function toggleServerProtocolFields() {
  const p = document.getElementById('srv-protocol').value;
  document.getElementById('srv-lbl-community').classList.toggle('hidden', p !== 'snmp');
  document.getElementById('srv-lbl-token').classList.toggle('hidden', p !== 'rest');
  document.getElementById('srv-lbl-user').classList.toggle('hidden', p === 'snmp');
  document.getElementById('srv-lbl-pass').classList.toggle('hidden', p === 'snmp');
}

document.getElementById('srv-protocol').addEventListener('change', toggleServerProtocolFields);
document.getElementById('show-add-server').addEventListener('click', async () => {
  await populateDatacenterSelects();
  document.getElementById('add-server-form').classList.toggle('hidden');
  toggleServerProtocolFields();
});
document.getElementById('cancel-add-server').addEventListener('click', () => document.getElementById('add-server-form').classList.add('hidden'));

document.getElementById('show-server-guide').addEventListener('click', async () => {
  const guide = await api('/servers/monitoring-guide');
  const el = document.getElementById('server-guide');
  el.classList.toggle('hidden');
  if (!el.classList.contains('hidden')) {
    el.innerHTML = `<h4>دليل الدخول والفحص — السيرفرات</h4><ul>${guide.protocols.map(p =>
      `<li><strong>${p.protocol.toUpperCase()}</strong> — منفذ <code>${p.port}</code>: ${p.description}<br>الحقول: ${p.fields.join(', ')}</li>`
    ).join('')}</ul>`;
  }
});

async function loadServers() {
  await populateDatacenterSelects();
  const servers = await api('/servers');
  document.querySelector('#servers-table tbody').innerHTML = servers.map(s => `
    <tr>
      <td>${s.name}</td><td>${s.ip_address}</td><td>${s.os_type}</td><td>${s.server_role}</td>
      <td class="status-${s.status}">${s.status}</td>
      <td>${s.last_seen ? new Date(s.last_seen).toLocaleString('ar') : '—'}</td>
      <td><button class="btn-sm" onclick="pollServer(${s.id})">فحص</button>
          <button class="btn-sm btn-secondary" onclick="showServerCreds(${s.id})">اعتماد</button></td>
    </tr>`).join('') || '<tr><td colspan="7" style="text-align:center;color:var(--muted)">لا توجد سيرفرات</td></tr>';
}

async function pollServer(id) {
  try {
    const r = await api(`/servers/${id}/poll`, { method: 'POST' });
    alert(r.success ? `متصل عبر ${r.protocol} — ${r.metrics || 0} مقياس` : `فشل: ${r.error}`);
    loadServers();
  } catch (e) { alert(e.message); }
}

async function showServerCreds(id) {
  const creds = await api(`/servers/${id}/credentials`);
  alert(creds.map(c => `${c.protocol} | user:${c.username || '-'} | port:${c.port || 'default'} | pwd:${c.has_password?'✓':'✗'}`).join('\n') || 'لا اعتماد');
}

document.getElementById('server-create-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const p = document.getElementById('srv-protocol').value;
  const port = document.getElementById('srv-port').value;
  const cred = { protocol: p, port: port ? parseInt(port) : null };
  if (p === 'snmp') cred.community = document.getElementById('srv-community').value;
  else {
    cred.username = document.getElementById('srv-username').value;
    cred.password = document.getElementById('srv-password').value;
    if (p === 'rest') cred.api_token = document.getElementById('srv-token').value;
  }
  const body = {
    datacenter_id: parseInt(document.getElementById('srv-dc').value),
    name: document.getElementById('srv-name').value,
    hostname: document.getElementById('srv-hostname').value,
    ip_address: document.getElementById('srv-ip').value,
    os_type: document.getElementById('srv-os').value,
    server_role: document.getElementById('srv-role').value,
    credentials: [cred],
  };
  try {
    const s = await api('/servers', { method: 'POST', body });
    document.getElementById('add-server-form').classList.add('hidden');
    loadServers();
    if (confirm('تمت الإضافة. فحص الآن؟')) pollServer(s.id);
  } catch (err) { alert(err.message); }
});

document.getElementById('poll-all-servers').addEventListener('click', async () => {
  const r = await api('/servers/poll-all', { method: 'POST' });
  alert(`سيرفرات: ${r.online}/${r.total} متصل`);
  loadServers();
});
document.getElementById('refresh-servers').addEventListener('click', loadServers);

// ─── Storage ───
function toggleStorageProtocolFields() {
  const p = document.getElementById('sto-protocol').value;
  document.getElementById('sto-lbl-community').classList.toggle('hidden', p !== 'snmp');
  document.getElementById('sto-lbl-token').classList.toggle('hidden', p !== 'rest');
  document.getElementById('sto-lbl-user').classList.toggle('hidden', p !== 'ssh');
  document.getElementById('sto-lbl-pass').classList.toggle('hidden', p !== 'ssh');
}

document.getElementById('sto-protocol').addEventListener('change', toggleStorageProtocolFields);
document.getElementById('show-add-storage').addEventListener('click', async () => {
  await populateDatacenterSelects();
  document.getElementById('add-storage-form').classList.toggle('hidden');
  toggleStorageProtocolFields();
});
document.getElementById('cancel-add-storage').addEventListener('click', () => document.getElementById('add-storage-form').classList.add('hidden'));

document.getElementById('show-storage-guide').addEventListener('click', async () => {
  const guide = await api('/storage/monitoring-guide');
  const el = document.getElementById('storage-guide');
  el.classList.toggle('hidden');
  if (!el.classList.contains('hidden')) {
    el.innerHTML = `<h4>دليل الدخول والفحص — التخزين</h4><ul>${guide.protocols.map(p =>
      `<li><strong>${p.protocol.toUpperCase()}</strong> — منفذ <code>${p.port}</code>: ${p.description}<br>الحقول: ${p.fields.join(', ')}</li>`
    ).join('')}</ul>`;
  }
});

async function loadStorage() {
  await populateDatacenterSelects();
  const items = await api('/storage');
  document.querySelector('#storage-table tbody').innerHTML = items.map(s => {
    const usage = s.total_capacity_tb && s.used_capacity_tb
      ? `${((s.used_capacity_tb / s.total_capacity_tb) * 100).toFixed(1)}%` : '—';
    const cap = s.total_capacity_tb ? `${s.used_capacity_tb || 0}/${s.total_capacity_tb} TB` : '—';
    return `<tr>
      <td>${s.name}</td><td>${s.ip_address}</td><td>${s.vendor}${s.model ? ' / ' + s.model : ''}</td><td>${cap}</td><td>${usage}</td>
      <td class="status-${s.status}">${s.status}</td>
      <td><button class="btn-sm" onclick="pollStorage(${s.id})">فحص</button>
          <button class="btn-sm btn-secondary" onclick="showStorageCreds(${s.id})">اعتماد</button></td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" style="text-align:center;color:var(--muted)">لا أنظمة تخزين</td></tr>';
}

async function pollStorage(id) {
  try {
    const r = await api(`/storage/${id}/poll`, { method: 'POST' });
    alert(r.success ? `متصل — استخدام ${r.capacity_usage_pct || '?'}%` : `فشل: ${r.error}`);
    loadStorage();
  } catch (e) { alert(e.message); }
}

async function showStorageCreds(id) {
  const creds = await api(`/storage/${id}/credentials`);
  alert(creds.map(c => `${c.protocol} | port:${c.port || 'default'} | community:${c.has_community?'✓':'✗'} | token:${c.has_token?'✓':'✗'}`).join('\n') || 'لا اعتماد');
}

document.getElementById('storage-create-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const p = document.getElementById('sto-protocol').value;
  const port = document.getElementById('sto-port').value;
  const cred = { protocol: p, port: port ? parseInt(port) : null };
  if (p === 'snmp') cred.community = document.getElementById('sto-community').value;
  else if (p === 'rest') cred.api_token = document.getElementById('sto-token').value;
  else { cred.username = document.getElementById('sto-username').value; cred.password = document.getElementById('sto-password').value; }
  const cap = document.getElementById('sto-capacity').value;
  const body = {
    datacenter_id: parseInt(document.getElementById('sto-dc').value),
    name: document.getElementById('sto-name').value,
    hostname: document.getElementById('sto-hostname').value,
    ip_address: document.getElementById('sto-ip').value,
    vendor: document.getElementById('sto-vendor').value,
    model: document.getElementById('sto-model').value || null,
    storage_type: document.getElementById('sto-type').value,
    total_capacity_tb: cap ? parseFloat(cap) : null,
    credentials: [cred],
  };
  try {
    const s = await api('/storage', { method: 'POST', body });
    document.getElementById('add-storage-form').classList.add('hidden');
    loadStorage();
    if (confirm('تمت الإضافة. فحص الآن؟')) pollStorage(s.id);
  } catch (err) { alert(err.message); }
});

document.getElementById('poll-all-storage').addEventListener('click', async () => {
  const r = await api('/storage/poll-all', { method: 'POST' });
  alert(`تخزين: ${r.online}/${r.total} متصل`);
  loadStorage();
});
document.getElementById('refresh-storage').addEventListener('click', loadStorage);

// ─── User Management ───
let allPermissions = [];
let roleTemplates = [];

async function loadPermCheckboxes(selected = []) {
  if (!allPermissions.length) allPermissions = await api('/users/permissions');
  const container = document.getElementById('perm-checkboxes');
  const groups = {};
  allPermissions.forEach(p => {
    if (!groups[p.group]) groups[p.group] = [];
    groups[p.group].push(p);
  });
  container.innerHTML = Object.entries(groups).map(([group, perms]) => `
    <div class="perm-group-title">${group}</div>
    ${perms.map(p => `
      <label title="${p.description}">
        <input type="checkbox" class="perm-check" value="${p.key}" ${selected.includes(p.key) ? 'checked' : ''}>
        <span>${p.label}</span>
      </label>`).join('')}
  `).join('');
}

function getSelectedPermissions() {
  return [...document.querySelectorAll('.perm-check:checked')].map(c => c.value);
}

document.getElementById('usr-role-template').addEventListener('change', async (e) => {
  const key = e.target.value;
  if (!roleTemplates.length) roleTemplates = await api('/users/roles');
  const tmpl = roleTemplates.find(r => r.key === key);
  if (tmpl && key !== 'custom') await loadPermCheckboxes(tmpl.permissions);
});

document.getElementById('show-add-user').addEventListener('click', async () => {
  document.getElementById('user-form-title').textContent = 'إضافة مستخدم';
  document.getElementById('user-edit-id').value = '';
  document.getElementById('user-form').reset();
  document.getElementById('usr-password').required = true;
  document.getElementById('usr-username').disabled = false;
  await loadPermCheckboxes(['view', 'view_reports']);
  document.getElementById('add-user-form').classList.remove('hidden');
});

document.getElementById('cancel-user-form').addEventListener('click', () => {
  document.getElementById('add-user-form').classList.add('hidden');
});

async function loadUsers() {
  if (!hasPerm('manage_users')) return;
  const users = await api('/users');
  const tbody = document.querySelector('#users-table tbody');
  tbody.innerHTML = users.map(u => `
    <tr>
      <td><strong>${u.username}</strong><br><small>${u.full_name || ''}</small></td>
      <td>${u.email}</td>
      <td>${ROLE_LABELS[u.role] || u.role}</td>
      <td>${(u.permissions || []).slice(0, 3).map(p => `<span class="badge-perm">${p}</span>`).join('')}${(u.permissions||[]).length > 3 ? ' +' + ((u.permissions||[]).length-3) : ''}</td>
      <td class="${u.is_active ? 'badge-active' : 'badge-inactive'}">${u.is_active ? 'نشط' : 'معطّل'}</td>
      <td>
        <button class="btn-sm" onclick="editUser(${u.id})">تعديل</button>
        ${u.id !== currentUser?.id ? `<button class="btn-sm btn-secondary" onclick="deleteUser(${u.id})">حذف</button>` : ''}
      </td>
    </tr>`).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--muted)">لا مستخدمين</td></tr>';
}

async function editUser(id) {
  const u = await api(`/users/${id}`);
  document.getElementById('user-form-title').textContent = 'تعديل مستخدم';
  document.getElementById('user-edit-id').value = id;
  document.getElementById('usr-username').value = u.username;
  document.getElementById('usr-username').disabled = true;
  document.getElementById('usr-email').value = u.email;
  document.getElementById('usr-fullname').value = u.full_name || '';
  document.getElementById('usr-password').value = '';
  document.getElementById('usr-password').required = false;
  document.getElementById('usr-role-template').value = u.role;
  document.getElementById('usr-active').value = String(u.is_active);
  await loadPermCheckboxes(u.permissions || []);
  document.getElementById('add-user-form').classList.remove('hidden');
}

async function deleteUser(id) {
  if (!confirm('حذف هذا المستخدم؟')) return;
  await api(`/users/${id}`, { method: 'DELETE' });
  loadUsers();
}

document.getElementById('user-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const editId = document.getElementById('user-edit-id').value;
  const role = document.getElementById('usr-role-template').value;
  const perms = getSelectedPermissions();
  const body = {
    email: document.getElementById('usr-email').value,
    full_name: document.getElementById('usr-fullname').value || null,
    role,
    permissions: role === 'custom' ? perms : perms,
    is_active: document.getElementById('usr-active').value === 'true',
  };
  const pwd = document.getElementById('usr-password').value;
  if (pwd) body.password = pwd;

  try {
    if (editId) {
      await api(`/users/${editId}`, { method: 'PUT', body });
    } else {
      body.username = document.getElementById('usr-username').value;
      body.password = pwd;
      await api('/users', { method: 'POST', body });
    }
    document.getElementById('add-user-form').classList.add('hidden');
    loadUsers();
  } catch (err) { alert(err.message); }
});

document.getElementById('refresh-users').addEventListener('click', loadUsers);

// --- Sensors (PRTG-style) ---

async function loadSensors() {
  const dcId = document.getElementById('sensor-dc-filter').value;
  const status = document.getElementById('sensor-status-filter').value;
  let path = '/sensors?';
  if (dcId) path += `datacenter_id=${dcId}&`;
  if (status) path += `status_filter=${status}&`;

  const [sensors, summary, dcs] = await Promise.all([
    api(path),
    api(`/sensors/summary${dcId ? `?datacenter_id=${dcId}` : ''}`),
    api('/datacenters'),
  ]);

  const dcSelect = document.getElementById('sensor-dc-filter');
  if (dcSelect.options.length <= 1) {
    dcSelect.innerHTML = '<option value="">كل المراكز</option>' +
      dcs.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
    if (dcId) dcSelect.value = dcId;
  }

  document.getElementById('sensor-summary-bar').innerHTML = `
    <div class="chip"><span class="sensor-dot up"></span>طبيعي: <strong>${summary.up || 0}</strong></div>
    <div class="chip"><span class="sensor-dot warning"></span>تحذير: <strong>${summary.warning || 0}</strong></div>
    <div class="chip"><span class="sensor-dot down"></span>تعطل: <strong>${summary.down || 0}</strong></div>
    <div class="chip"><span class="sensor-dot paused"></span>موقوف: <strong>${summary.paused || 0}</strong></div>
    <div class="chip"><span class="sensor-dot unknown"></span>غير معروف: <strong>${summary.unknown || 0}</strong></div>
    <div class="chip">الإجمالي: <strong>${summary.total || 0}</strong></div>
  `;

  const tbody = document.querySelector('#sensors-table tbody');
  tbody.innerHTML = sensors.map(s => {
    const val = s.last_value != null ? `${s.last_value}${s.unit || ''}` : '—';
    return `<tr>
      <td><span class="sensor-dot ${s.last_status}" title="${s.status_label}"></span></td>
      <td>${s.name}</td>
      <td>${s.asset_name || '—'}</td>
      <td>${ASSET_TYPE_LABELS[s.asset_type] || s.asset_type}</td>
      <td><strong>${val}</strong></td>
      <td>${s.warning_limit ?? '—'}</td>
      <td>${s.error_limit ?? '—'}</td>
      <td class="sensor-status-${s.last_status}">${s.status_label}</td>
      <td>${s.last_check_at ? new Date(s.last_check_at).toLocaleString('ar') : '—'}</td>
      <td><button class="btn-sm" onclick="openSensorDetail(${s.id})">تفاصيل</button></td>
    </tr>`;
  }).join('') || '<tr><td colspan="10" style="text-align:center;color:var(--muted)">لا توجد حساسات — شغّل فحص الأصول أو أنشئ حساسات افتراضية</td></tr>';
}

async function openSensorDetail(id) {
  const sensor = await api(`/sensors/${id}`);
  const history = await api(`/sensors/${id}/history?limit=40`);
  document.getElementById('sensor-detail').classList.remove('hidden');
  document.getElementById('sensor-detail-title').textContent = `${sensor.name} — ${sensor.asset_name || ''}`;
  document.getElementById('sensor-edit-id').value = sensor.id;
  document.getElementById('sensor-edit-name').value = sensor.name;
  document.getElementById('sensor-edit-warning').value = sensor.warning_limit ?? '';
  document.getElementById('sensor-edit-error').value = sensor.error_limit ?? '';
  document.getElementById('sensor-edit-direction').value = String(sensor.higher_is_worse);
  document.getElementById('sensor-edit-enabled').value = String(sensor.enabled);

  const chart = document.getElementById('sensor-history-chart');
  if (!history.length) {
    chart.innerHTML = '<p class="muted">لا يوجد سجل بعد — انتظر دورة الفحص</p>';
    return;
  }
  const max = Math.max(...history.map(h => h.value), 1);
  const warn = sensor.warning_limit;
  const err = sensor.error_limit;
  chart.innerHTML = history.map(h => {
    const pct = Math.max(4, (h.value / max) * 100);
    let cls = '';
    if (err != null && h.value >= err) cls = 'down';
    else if (warn != null && h.value >= warn) cls = 'warn';
    return `<div class="bar ${cls}" style="height:${pct}%" title="${h.value}${h.unit || ''}"></div>`;
  }).join('');
}

document.getElementById('refresh-sensors')?.addEventListener('click', loadSensors);
document.getElementById('sensor-dc-filter')?.addEventListener('change', loadSensors);
document.getElementById('sensor-status-filter')?.addEventListener('change', loadSensors);
document.getElementById('close-sensor-detail')?.addEventListener('click', () => {
  document.getElementById('sensor-detail').classList.add('hidden');
});
document.getElementById('save-sensor-btn')?.addEventListener('click', async () => {
  const id = document.getElementById('sensor-edit-id').value;
  const body = {
    name: document.getElementById('sensor-edit-name').value,
    warning_limit: parseFloat(document.getElementById('sensor-edit-warning').value) || null,
    error_limit: parseFloat(document.getElementById('sensor-edit-error').value) || null,
    higher_is_worse: document.getElementById('sensor-edit-direction').value === 'true',
    enabled: document.getElementById('sensor-edit-enabled').value === 'true',
  };
  try {
    await api(`/sensors/${id}`, { method: 'PATCH', body });
    await loadSensors();
    await openSensorDetail(id);
  } catch (err) {
    alert(err.message);
  }
});
document.getElementById('seed-sensors')?.addEventListener('click', async () => {
  try {
    const r = await api('/sensors/seed', { method: 'POST' });
    alert(`تم إنشاء ${r.created} حساس`);
    loadSensors();
  } catch (err) { alert(err.message); }
});

// --- Excel Import ---
let excelSelectedFile = null;
let excelPreviewData = null;

function resetExcelImportUI() {
  excelSelectedFile = null;
  excelPreviewData = null;
  document.getElementById('excel-file-input').value = '';
  document.getElementById('excel-file-name').textContent = '';
  document.getElementById('excel-preview-btn').disabled = true;
  document.getElementById('excel-apply-btn').disabled = true;
  document.getElementById('excel-status').textContent = '';
  document.getElementById('excel-preview').classList.add('hidden');
}

function setExcelFile(file) {
  if (!file) return;
  const ext = file.name.split('.').pop()?.toLowerCase();
  if (!['xlsx', 'xls'].includes(ext)) {
    document.getElementById('excel-status').textContent = 'يُقبل ملف Excel فقط (.xlsx)';
    return;
  }
  excelSelectedFile = file;
  excelPreviewData = null;
  document.getElementById('excel-file-name').textContent = file.name;
  document.getElementById('excel-preview-btn').disabled = false;
  document.getElementById('excel-apply-btn').disabled = true;
  document.getElementById('excel-status').textContent = '';
  document.getElementById('excel-preview').classList.add('hidden');
}

function renderExcelPreview(data) {
  excelPreviewData = data;
  document.getElementById('excel-preview').classList.remove('hidden');
  const s = data.summary || {};
  document.getElementById('excel-summary').innerHTML = `
    <div class="stat-card"><div class="value">${s.total || 0}</div><div class="label">إجمالي الأصول</div></div>
    <div class="stat-card"><div class="value">${s.devices || 0}</div><div class="label">أجهزة شبكة</div></div>
    <div class="stat-card"><div class="value">${s.servers || 0}</div><div class="label">سيرفرات</div></div>
    <div class="stat-card"><div class="value">${s.storage || 0}</div><div class="label">تخزين</div></div>
    <div class="stat-card"><div class="value">${s.links || 0}</div><div class="label">روابط</div></div>
    <div class="stat-card"><div class="value">${s.datacenters || 0}</div><div class="label">مراكز بيانات</div></div>
  `;
  const errBox = document.getElementById('excel-errors');
  if (data.errors?.length) {
    errBox.classList.remove('hidden');
    errBox.innerHTML = '<strong>تحذيرات:</strong><ul>' + data.errors.map(e => `<li>${e}</li>`).join('') + '</ul>';
  } else {
    errBox.classList.add('hidden');
    errBox.innerHTML = '';
  }
  document.getElementById('excel-dc-list').innerHTML = (data.datacenters || []).length
    ? data.datacenters.map(d => `<span class="tag">${d}</span>`).join(' ')
    : '<span class="muted">لا توجد</span>';
  document.querySelector('#excel-assets-table tbody').innerHTML = (data.assets || []).map(a => `
    <tr>
      <td>${a.row}</td><td>${a.datacenter}</td><td>${a.asset_type}</td>
      <td>${a.name}</td><td>${a.ip_address}</td><td>${a.vendor || '—'}</td><td>${a.protocol || '—'}</td>
    </tr>
  `).join('') || '<tr><td colspan="7" style="text-align:center;color:var(--muted)">لا توجد أصول</td></tr>';
  document.querySelector('#excel-links-table tbody').innerHTML = (data.links || []).map(l => `
    <tr>
      <td>${l.row}</td><td>${l.datacenter}</td>
      <td>${l.from_name || l.from || '—'}</td><td>${l.to_name || l.to || '—'}</td><td>${l.label || '—'}</td>
    </tr>
  `).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--muted)">لا توجد روابط</td></tr>';
  document.getElementById('excel-apply-btn').disabled = !(data.assets?.length);
}

document.getElementById('excel-browse-btn')?.addEventListener('click', () => {
  document.getElementById('excel-file-input').click();
});

document.getElementById('excel-file-input')?.addEventListener('change', (e) => {
  setExcelFile(e.target.files[0]);
});

const excelDropzone = document.getElementById('excel-dropzone');
excelDropzone?.addEventListener('dragover', (e) => {
  e.preventDefault();
  excelDropzone.classList.add('dragover');
});
excelDropzone?.addEventListener('dragleave', () => excelDropzone.classList.remove('dragover'));
excelDropzone?.addEventListener('drop', (e) => {
  e.preventDefault();
  excelDropzone.classList.remove('dragover');
  setExcelFile(e.dataTransfer.files[0]);
});

document.getElementById('download-excel-template')?.addEventListener('click', async () => {
  try {
    const blob = await api('/import/excel/template');
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'dcms-import-template.xlsx';
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    document.getElementById('excel-status').textContent = err.message;
  }
});

document.getElementById('excel-preview-btn')?.addEventListener('click', async () => {
  if (!excelSelectedFile) return;
  const statusEl = document.getElementById('excel-status');
  statusEl.textContent = 'جاري التحليل...';
  try {
    const form = new FormData();
    form.append('file', excelSelectedFile);
    const data = await api('/import/excel/preview', { method: 'POST', body: form });
    renderExcelPreview(data);
    statusEl.textContent = 'تم التحليل — راجع المعاينة ثم أكّد الاستيراد';
  } catch (err) {
    statusEl.textContent = err.message;
  }
});

document.getElementById('excel-apply-btn')?.addEventListener('click', async () => {
  if (!excelSelectedFile) return;
  if (!confirm('هل تريد استيراد الأصول وإنشاء/تحديث المخططات ومراكز البيانات؟')) return;
  const statusEl = document.getElementById('excel-status');
  statusEl.textContent = 'جاري الاستيراد...';
  try {
    const form = new FormData();
    form.append('file', excelSelectedFile);
    const skip = document.getElementById('excel-skip-existing').checked;
    const data = await api(`/import/excel/apply?skip_existing=${skip}`, { method: 'POST', body: form });
    statusEl.textContent = `تم الاستيراد: ${data.imported} أصل، ${data.skipped} متخطى، ${data.datacenters} مركز بيانات، ${data.maps_updated} مخطط`;
    if (data.errors?.length) {
      statusEl.textContent += ' — تحذيرات: ' + data.errors.join('; ');
    }
    await loadDashboard();
  } catch (err) {
    statusEl.textContent = err.message;
  }
});

window.openDatacenterDetail = openDatacenterDetail;
window.ackAlert = ackAlert;
window.resolveAlert = resolveAlert;
window.downloadDcReport = downloadDcReport;

if (token) {
  initApp().catch(() => logout());
} else {
  showPanel('login');
}
