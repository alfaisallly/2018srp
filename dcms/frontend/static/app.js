const API = '/api/v1';
let token = localStorage.getItem('dcms_token');
let network = null;

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

function logout() {
  token = null;
  localStorage.removeItem('dcms_token');
  showPanel('login');
}

function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.add('hidden'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  if (name === 'login') {
    document.getElementById('login-panel').classList.remove('hidden');
    document.querySelector('nav').style.display = 'none';
    return;
  }
  document.querySelector('nav').style.display = 'flex';
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
    if (panel === 'network-map') loadNetworkMap();
    if (panel === 'alerts') loadAlerts();
    if (panel === 'reports') loadReportSelector();
    if (panel === 'dashboard') loadDashboard();
  });
});

async function initApp() {
  const user = await api('/auth/me');
  document.getElementById('user-info').textContent = `${user.full_name || user.username} (${user.role})`;
  showPanel('dashboard');
  await loadDashboard();
}

async function loadDashboard() {
  const stats = await api('/reports/dashboard');
  document.getElementById('stats-grid').innerHTML = `
    <div class="stat-card"><div class="value">${stats.datacenters}</div><div class="label">مراكز البيانات</div></div>
    <div class="stat-card"><div class="value">${stats.total_devices}</div><div class="label">إجمالي الأجهزة</div></div>
    <div class="stat-card"><div class="value status-online">${stats.online_devices}</div><div class="label">متصل</div></div>
    <div class="stat-card"><div class="value status-offline">${stats.offline_devices}</div><div class="label">غير متصل</div></div>
    <div class="stat-card"><div class="value">${stats.open_alerts}</div><div class="label">تنبيهات مفتوحة</div></div>
    <div class="stat-card"><div class="value severity-critical">${stats.critical_alerts}</div><div class="label">حرجة</div></div>
  `;
  const dcs = await api('/datacenters');
  document.getElementById('datacenters-list').innerHTML = dcs.length
    ? dcs.map(d => `<p><strong>${d.name}</strong> — ${d.location || 'بدون موقع'}</p>`).join('')
    : '<p style="color:var(--muted)">لا توجد مراكز بيانات بعد</p>';
}

async function loadDevices() {
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
      <td>${new Date(a.created_at).toLocaleString('ar')}</td>
      <td>${a.status === 'open' ? `<button class="btn-sm" onclick="resolveAlert(${a.id})">حل</button>` : '—'}</td>
    </tr>
  `).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--muted)">لا توجد تنبيهات</td></tr>';
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

if (token) {
  initApp().catch(() => logout());
} else {
  showPanel('login');
}
