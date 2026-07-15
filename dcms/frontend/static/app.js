const API = '/api/v1';
let token = localStorage.getItem('dcms_token');
let network = null;
let dcNetwork = null;
let currentUser = null;
let currentPermissions = new Set();
let currentDcOverview = null;
let selectedDatacenterId = null;
const t = (k, p) => window.t(k, p);
const labelOr = (key, fallback) => {
  const val = t(key);
  return val === key ? fallback : val;
};
const roleLabel = (role) => labelOr(`role.${role}`, role);
const deviceTypeLabel = (type) => labelOr(`device_type.${type}`, type);
const assetTypeLabel = (type) => labelOr(`asset_type.${type}`, type);
const vendorLabel = (vendor) => labelOr(`vendor.${vendor}`, vendor);
function localeDate(d) {
  const lang = window.I18n?.getLanguage?.() || 'ar';
  return new Date(d).toLocaleString(lang === 'en' ? 'en-US' : 'ar');
}

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
  localStorage.removeItem('dcms_view_mode');
  localStorage.removeItem('dcms_global_dc_filter');
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
    if (!res.ok) throw new Error(t('login.error'));
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
  if (confirm(t('common.confirm_logout'))) logout();
});

function refreshCurrentPanel() {
  if (currentUser) {
    document.getElementById('user-info').textContent =
      `${currentUser.full_name || currentUser.username} (${roleLabel(currentUser.role)})`;
  }
  const detailView = document.getElementById('dc-detail-view');
  if (detailView && !detailView.classList.contains('hidden') && selectedDatacenterId) {
    const activeTab = document.querySelector('.dc-tab.active')?.dataset.dcTab || 'overview';
    openDatacenterDetail(selectedDatacenterId, activeTab);
    return;
  }
  const activePanel = document.querySelector('.nav-btn.active')?.dataset.panel;
  if (!activePanel || activePanel === 'login') return;
  if (activePanel === 'dashboard') loadDashboard();
  else if (activePanel === 'devices') loadDevices();
  else if (activePanel === 'servers') loadServers();
  else if (activePanel === 'storage') loadStorage();
  else if (activePanel === 'alerts') loadAlerts();
  else if (activePanel === 'sensors') loadSensors();
  else if (activePanel === 'network-map') loadNetworkMap();
  else if (activePanel === 'reports') loadReportSelector();
  else if (activePanel === 'users') loadUsers();
  else if (activePanel === 'import-excel') {
    if (excelPreviewData) renderExcelPreview(excelPreviewData);
    else resetExcelImportUI();
  }
}

document.addEventListener('dcms:langchange', refreshCurrentPanel);

async function initApp() {
  localStorage.removeItem('dcms_view_mode');
  localStorage.removeItem('dcms_global_dc_filter');
  const user = await api('/auth/me');
  currentUser = user;
  currentPermissions = new Set(user.permission_keys || []);
  document.getElementById('user-info').textContent = `${user.full_name || user.username} (${roleLabel(user.role)})`;
  applyPermissionsUI();
  showPanel('dashboard');
  await loadDashboard();
  const hashMatch = location.hash.match(/^#dc\/(\d+)$/);
  if (hashMatch) await openDatacenterDetail(Number(hashMatch[1]));
}

async function loadDashboard() {
  document.getElementById('dc-detail-view').classList.add('hidden');
  document.getElementById('stats-grid').classList.remove('hidden');
  selectedDatacenterId = null;
  currentDcOverview = null;
  clearDcHash();
  document.getElementById('dc-list-view').classList.remove('hidden');

  const stats = await api('/reports/dashboard');
  document.getElementById('stats-grid').innerHTML = `
    <div class="stat-card"><div class="value">${stats.datacenters}</div><div class="label">${t('stats.datacenters')}</div></div>
    <div class="stat-card"><div class="value">${stats.total_devices}</div><div class="label">${t('stats.devices')}</div></div>
    <div class="stat-card"><div class="value">${stats.total_servers || 0}</div><div class="label">${t('stats.servers')}</div></div>
    <div class="stat-card"><div class="value">${stats.total_storage || 0}</div><div class="label">${t('stats.storage')}</div></div>
    <div class="stat-card"><div class="value status-online">${stats.online_devices}</div><div class="label">${t('stats.online_network')}</div></div>
    <div class="stat-card"><div class="value">${stats.open_alerts}</div><div class="label">${t('stats.open_alerts')}</div></div>
    <div class="stat-card"><div class="value">${stats.total_sensors || 0}</div><div class="label">${t('stats.sensors')}</div></div>
  `;

  const dcs = await api('/datacenters');
  if (!dcs.length) {
    document.getElementById('datacenters-grid').innerHTML =
      `<p style="color:var(--muted);grid-column:1/-1">${t('dc.no_dcs')}</p>`;
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
      <p class="dc-meta">${d.location || t('dc.no_location')}${d.description ? ' — ' + d.description : ''}</p>
      <div class="dc-chips">
        <span class="chip-sm">🔀 ${s.switches || 0} ${t('dc.chip_switch')}</span>
        <span class="chip-sm">🛡️ ${s.firewalls || 0} ${t('dc.chip_firewall')}</span>
        <span class="chip-sm">🖥️ ${s.servers || 0} ${t('dc.chip_server')}</span>
        <span class="chip-sm">💾 ${s.storage || 0} ${t('dc.chip_storage')}</span>
        <span class="chip-sm">⚠️ ${s.open_alerts || 0} ${t('dc.chip_alert')}</span>
      </div>
    </div>`;
  }).join('');
}








function computeDcHealth(summary) {
  const totalAssets = (summary.total_devices || 0) + (summary.servers || 0) + (summary.storage || 0);
  const onlineAssets = (summary.online_devices || 0) + (summary.online_servers || 0) + (summary.online_storage || 0);
  const assetScore = totalAssets ? Math.round((onlineAssets / totalAssets) * 100) : 100;
  const sensorTotal = summary.total_sensors || 0;
  const sensorOk = summary.sensors_up || 0;
  const sensorScore = sensorTotal ? Math.round((sensorOk / sensorTotal) * 100) : 100;
  const score = Math.round((assetScore * 0.6) + (sensorScore * 0.4));
  let level = 'healthy';
  let labelKey = 'dc.portal.health_healthy';
  if ((summary.critical_alerts || 0) > 0 || (summary.sensors_down || 0) > 0 || score < 50) {
    level = 'critical';
    labelKey = 'dc.portal.health_critical';
  } else if ((summary.open_alerts || 0) > 0 || (summary.sensors_warning || 0) > 0 || score < 80) {
    level = 'warning';
    labelKey = 'dc.portal.health_warning';
  }
  return { level, score, labelKey, assetScore, sensorScore };
}

function setDcHash(dcId) {
  history.replaceState(null, '', `#dc/${dcId}`);
}

function clearDcHash() {
  if (location.hash.startsWith('#dc/')) history.replaceState(null, '', location.pathname + location.search);
}

function renderProgressBar(label, online, total, icon) {
  const pct = total ? Math.round((online / total) * 100) : 0;
  return `<div class="dc-progress-item">
    <div class="dc-progress-head"><span>${icon} ${label}</span><strong>${online}/${total} (${pct}%)</strong></div>
    <div class="dc-progress-track"><div class="dc-progress-fill" style="width:${pct}%"></div></div>
  </div>`;
}

function renderDcPortalChrome() {
  if (!currentDcOverview) return;
  const dc = currentDcOverview.datacenter;
  const s = currentDcOverview.summary;
  const health = computeDcHealth(s);

  document.getElementById('dc-detail-name').textContent = dc.name;
  document.getElementById('dc-detail-location').textContent =
    [dc.location, dc.description].filter(Boolean).join(' — ') || t('dc.no_details');

  const meta = [];
  if (dc.contact_email) meta.push(`✉ ${dc.contact_email}`);
  if (dc.created_at) meta.push(`${t('dc.portal.created')}: ${localeDate(dc.created_at)}`);
  document.getElementById('dc-hero-meta').innerHTML = meta.map(m => `<span class="dc-meta-chip">${m}</span>`).join('');

  const badge = document.getElementById('dc-health-badge');
  badge.className = `dc-health-badge ${health.level}`;
  badge.textContent = t(health.labelKey);

  const ring = document.getElementById('dc-health-ring');
  ring.className = `dc-health-ring ${health.level}`;
  document.getElementById('dc-health-score').textContent = `${health.score}%`;

  document.getElementById('dc-detail-stats').innerHTML = `
    <div class="dc-kpi-card"><div class="dc-kpi-icon">🔀</div><div class="dc-kpi-value">${s.switches}</div><div class="dc-kpi-label">${t('stats.switches')}</div></div>
    <div class="dc-kpi-card"><div class="dc-kpi-icon">🛡️</div><div class="dc-kpi-value">${s.firewalls}</div><div class="dc-kpi-label">${t('stats.firewalls')}</div></div>
    <div class="dc-kpi-card"><div class="dc-kpi-icon">🖥️</div><div class="dc-kpi-value">${s.servers}</div><div class="dc-kpi-label">${t('stats.servers_short')}</div></div>
    <div class="dc-kpi-card"><div class="dc-kpi-icon">💾</div><div class="dc-kpi-value">${s.storage}</div><div class="dc-kpi-label">${t('stats.storage_short')}</div></div>
    <div class="dc-kpi-card highlight"><div class="dc-kpi-icon">✅</div><div class="dc-kpi-value status-online">${s.online_devices + s.online_servers + s.online_storage}</div><div class="dc-kpi-label">${t('stats.online')}</div></div>
    <div class="dc-kpi-card ${s.open_alerts ? 'warn' : ''}"><div class="dc-kpi-icon">⚠️</div><div class="dc-kpi-value">${s.open_alerts}</div><div class="dc-kpi-label">${t('stats.alerts')}</div></div>
    <div class="dc-kpi-card"><div class="dc-kpi-icon">📡</div><div class="dc-kpi-value sensor-status-up">${s.sensors_up}</div><div class="dc-kpi-label">${t('stats.sensors_up')}</div></div>
    <div class="dc-kpi-card ${s.sensors_down ? 'danger' : ''}"><div class="dc-kpi-icon">⛔</div><div class="dc-kpi-value sensor-status-down">${s.sensors_down}</div><div class="dc-kpi-label">${t('stats.sensors_down')}</div></div>
  `;

  const setCount = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  setCount('dc-count-switches', s.switches);
  setCount('dc-count-firewalls', s.firewalls);
  setCount('dc-count-servers', s.servers);
  setCount('dc-count-storage', s.storage);
  setCount('dc-count-alerts', s.open_alerts);

  document.getElementById('dc-sidebar-health').innerHTML = `
    <h4>${t('dc.portal.quick_health')}</h4>
    ${renderProgressBar(t('stats.network_devices'), s.online_devices, s.total_devices, '🔀')}
    ${renderProgressBar(t('stats.servers_short'), s.online_servers, s.servers, '🖥️')}
    ${renderProgressBar(t('stats.storage_short'), s.online_storage, s.storage, '💾')}
    <div class="dc-sensor-mini">
      <span class="sensor-dot up"></span>${s.sensors_up}
      <span class="sensor-dot warning"></span>${s.sensors_warning || 0}
      <span class="sensor-dot down"></span>${s.sensors_down}
    </div>
  `;
}

function assetTableRowsWithActions(items, type) {
  const dash = t('common.dash');
  if (!items?.length) return `<tr><td colspan="7" style="text-align:center;color:var(--muted)">${t('common.no_assets')}</td></tr>`;
  const pollFn = type === 'server' ? 'pollServer' : type === 'storage' ? 'pollStorage' : 'pollDevice';
  return items.map(a => {
    const extra = type === 'server'
      ? `<td>${a.os_type || dash}</td><td>${a.server_role || dash}</td>`
      : type === 'storage'
        ? `<td>${a.vendor || dash}</td><td>${a.storage_type || dash}</td>`
        : `<td>${vendorLabel(a.vendor) || a.vendor || dash}</td><td>${deviceTypeLabel(a.device_type) || a.device_type || dash}</td>`;
    return `<tr>
      <td><strong>${a.name}</strong></td><td>${a.ip_address}</td>${extra}
      <td class="status-${a.status}">${a.status}</td>
      <td>${a.last_seen ? localeDate(a.last_seen) : dash}</td>
      <td><button class="btn-sm" onclick="${pollFn}(${a.id});openDatacenterDetail(${selectedDatacenterId})">${t('common.poll')}</button></td>
    </tr>`;
  }).join('');
}

async function openDatacenterDetail(dcId, tab = 'overview') {
  selectedDatacenterId = dcId;
  currentDcOverview = await api(`/datacenters/${dcId}/overview`);
  document.getElementById('stats-grid').classList.add('hidden');
  document.getElementById('dc-list-view').classList.add('hidden');
  document.getElementById('dc-detail-view').classList.remove('hidden');
  setDcHash(dcId);
  renderDcPortalChrome();
  document.querySelectorAll('.dc-tab').forEach(btn => btn.classList.toggle('active', btn.dataset.dcTab === tab));
  renderDcTab(tab);
}

async function refreshDatacenterPortal() {
  if (!selectedDatacenterId) return;
  const activeTab = document.querySelector('.dc-tab.active')?.dataset.dcTab || 'overview';
  await openDatacenterDetail(selectedDatacenterId, activeTab);
}

async function pollDcAssets() {
  if (!selectedDatacenterId || !currentDcOverview) return;
  const ov = currentDcOverview;
  const deviceIds = [...ov.switches, ...ov.firewalls, ...ov.routers, ...ov.other_devices].map(d => d.id);
  for (const id of deviceIds) {
    try { await api(`/devices/${id}/poll`, { method: 'POST' }); } catch (_) {}
  }
  for (const s of ov.servers) {
    try { await api(`/servers/${s.id}/poll`, { method: 'POST' }); } catch (_) {}
  }
  for (const st of ov.storage) {
    try { await api(`/storage/${st.id}/poll`, { method: 'POST' }); } catch (_) {}
  }
  await refreshDatacenterPortal();
}

function renderDcTab(tab) {
  if (!currentDcOverview) return;
  const el = document.getElementById('dc-tab-content');
  const s = currentDcOverview.summary;
  const dc = currentDcOverview.datacenter;

  if (tab === 'overview') {
    const none = t('common.none');
    const health = computeDcHealth(s);
    el.innerHTML = `
      <div class="dc-section-head">
        <h3>${t('dc.overview_title', { name: dc.name })}</h3>
        <p class="muted">${t('dc.portal.overview_desc')}</p>
      </div>
      <div class="dc-overview-dashboard">
        <div class="dc-panel-grid">
          <div class="dc-panel-card">
            <h4>${t('dc.portal.asset_health')}</h4>
            ${renderProgressBar(t('stats.network_devices'), s.online_devices, s.total_devices, '🔀')}
            ${renderProgressBar(t('stats.servers_short'), s.online_servers, s.servers, '🖥️')}
            ${renderProgressBar(t('stats.storage_short'), s.online_storage, s.storage, '💾')}
          </div>
          <div class="dc-panel-card">
            <h4>${t('dc.portal.sensor_status')}</h4>
            <div class="dc-sensor-bars">
              <div class="dc-sensor-bar up" style="flex:${s.sensors_up || 0.1}"><span>${t('sensors.up')}</span><strong>${s.sensors_up}</strong></div>
              <div class="dc-sensor-bar warning" style="flex:${s.sensors_warning || 0.1}"><span>${t('sensors.warning')}</span><strong>${s.sensors_warning || 0}</strong></div>
              <div class="dc-sensor-bar down" style="flex:${s.sensors_down || 0.1}"><span>${t('sensors.down')}</span><strong>${s.sensors_down}</strong></div>
            </div>
            <p class="muted dc-panel-foot">${t('dc.portal.total_sensors', { count: s.total_sensors })}</p>
          </div>
          <div class="dc-panel-card">
            <h4>${t('dc.portal.recent_alerts')}</h4>
            <ul class="dc-alert-feed">
              ${currentDcOverview.alerts.slice(0, 6).map(a => `
                <li class="severity-${a.severity}">
                  <strong>${a.title}</strong>
                  <span>${a.severity} — ${localeDate(a.created_at)}</span>
                </li>`).join('') || `<li class="muted">${t('alerts.no_open')}</li>`}
            </ul>
          </div>
        </div>
        <div class="dc-quick-nav">
          <button class="dc-quick-card" onclick="switchDcTab('switches')"><span>🔀</span><strong>${s.switches}</strong><em>${t('dc.tab.switches')}</em></button>
          <button class="dc-quick-card" onclick="switchDcTab('firewalls')"><span>🛡️</span><strong>${s.firewalls}</strong><em>${t('dc.tab.firewalls')}</em></button>
          <button class="dc-quick-card" onclick="switchDcTab('servers')"><span>🖥️</span><strong>${s.servers}</strong><em>${t('dc.tab.servers')}</em></button>
          <button class="dc-quick-card" onclick="switchDcTab('storage')"><span>💾</span><strong>${s.storage}</strong><em>${t('dc.tab.storage')}</em></button>
          <button class="dc-quick-card" onclick="switchDcTab('monitoring')"><span>📡</span><strong>${s.total_sensors}</strong><em>${t('dc.tab.monitoring')}</em></button>
          <button class="dc-quick-card" onclick="switchDcTab('topology')"><span>🗺️</span><strong>${s.network_maps}</strong><em>${t('dc.tab.topology')}</em></button>
        </div>
        <div class="dc-overview-grid">
          <div class="dc-overview-card"><h4>${t('section.switches', { count: s.switches })}</h4><ul>${currentDcOverview.switches.slice(0,5).map(d=>`<li>${d.name} — ${d.ip_address} <span class="status-${d.status}">${d.status}</span></li>`).join('') || `<li>${none}</li>`}</ul></div>
          <div class="dc-overview-card"><h4>${t('section.servers', { count: s.servers })}</h4><ul>${currentDcOverview.servers.slice(0,5).map(d=>`<li>${d.name} — ${d.ip_address} <span class="status-${d.status}">${d.status}</span></li>`).join('') || `<li>${none}</li>`}</ul></div>
          <div class="dc-overview-card"><h4>${t('section.storage', { count: s.storage })}</h4><ul>${currentDcOverview.storage.slice(0,5).map(d=>`<li>${d.name} — ${d.ip_address} <span class="status-${d.status}">${d.status}</span></li>`).join('') || `<li>${none}</li>`}</ul></div>
        </div>
      </div>`;
    return;
  }

  if (tab === 'monitoring') {
    const sensors = currentDcOverview.sensors;
    const dash = t('common.dash');
    el.innerHTML = `
      <div class="dc-section-head">
        <h3>${t('dc.monitoring_title', { name: dc.name })}</h3>
        <p class="muted">${t('dc.portal.monitoring_desc')}</p>
      </div>
      <div class="sensor-summary-bar dc-monitor-summary">
        <div class="chip"><span class="sensor-dot up"></span>${t('sensors.up')}: <strong>${s.sensors_up}</strong></div>
        <div class="chip"><span class="sensor-dot warning"></span>${t('sensors.warning')}: <strong>${s.sensors_warning || 0}</strong></div>
        <div class="chip"><span class="sensor-dot down"></span>${t('sensors.down')}: <strong>${s.sensors_down}</strong></div>
        <div class="chip">${t('sensors.total')}: <strong>${s.total_sensors}</strong></div>
      </div>
      <table><thead><tr><th></th><th>${t('sensors.sensor')}</th><th>${t('common.type')}</th><th>${t('sensors.value')}</th><th>${t('common.status')}</th><th>${t('sensors.last_check')}</th><th>${t('common.action')}</th></tr></thead><tbody>
      ${sensors.length ? sensors.map(sen => `<tr>
        <td><span class="sensor-dot ${sen.last_status}"></span></td>
        <td>${sen.name}</td><td>${assetTypeLabel(sen.asset_type) || sen.asset_type}</td>
        <td><strong>${sen.last_value != null ? sen.last_value + (sen.unit || '') : dash}</strong></td>
        <td class="sensor-status-${sen.last_status}">${sen.status_label}</td>
        <td>${sen.last_check_at ? localeDate(sen.last_check_at) : dash}</td>
        <td><button class="btn-sm" onclick="openSensorDetail(${sen.id})">${t('sensors.detail')}</button></td>
      </tr>`).join('') : `<tr><td colspan="7" style="text-align:center;color:var(--muted)">${t('sensors.no_sensors_dc')}</td></tr>`}
    </tbody></table>`;
    return;
  }

  if (tab === 'switches') {
    el.innerHTML = `<div class="dc-section-head"><h3>${t('dc.tab.switches')}</h3><p class="muted">${t('dc.portal.switches_desc')}</p></div>
      <table><thead><tr><th>${t('common.name')}</th><th>${t('common.ip')}</th><th>${t('common.vendor')}</th><th>${t('common.type')}</th><th>${t('common.status')}</th><th>${t('common.last_seen')}</th><th>${t('common.action')}</th></tr></thead><tbody>${assetTableRowsWithActions(currentDcOverview.switches, 'device')}</tbody></table>`;
    return;
  }

  if (tab === 'firewalls') {
    el.innerHTML = `<div class="dc-section-head"><h3>${t('dc.tab.firewalls')}</h3><p class="muted">${t('dc.portal.firewalls_desc')}</p></div>
      <table><thead><tr><th>${t('common.name')}</th><th>${t('common.ip')}</th><th>${t('common.vendor')}</th><th>${t('common.type')}</th><th>${t('common.status')}</th><th>${t('common.last_seen')}</th><th>${t('common.action')}</th></tr></thead><tbody>${assetTableRowsWithActions(currentDcOverview.firewalls, 'device')}</tbody></table>`;
    return;
  }

  if (tab === 'servers') {
    el.innerHTML = `<div class="dc-section-head"><h3>${t('dc.tab.servers')}</h3><p class="muted">${t('dc.portal.servers_desc')}</p></div>
      <table><thead><tr><th>${t('common.name')}</th><th>${t('common.ip')}</th><th>${t('servers.os')}</th><th>${t('common.role_col')}</th><th>${t('common.status')}</th><th>${t('common.last_seen')}</th><th>${t('common.action')}</th></tr></thead><tbody>${assetTableRowsWithActions(currentDcOverview.servers, 'server')}</tbody></table>`;
    return;
  }

  if (tab === 'storage') {
    el.innerHTML = `<div class="dc-section-head"><h3>${t('storage.title')}</h3><p class="muted">${t('dc.portal.storage_desc')}</p></div>
      <table><thead><tr><th>${t('common.name')}</th><th>${t('common.ip')}</th><th>${t('common.vendor')}</th><th>${t('common.type')}</th><th>${t('common.status')}</th><th>${t('common.last_seen')}</th><th>${t('common.action')}</th></tr></thead><tbody>${assetTableRowsWithActions(currentDcOverview.storage, 'storage')}</tbody></table>`;
    return;
  }

  if (tab === 'topology') {
    const maps = currentDcOverview.network_maps;
    if (!maps.length) {
      el.innerHTML = `<div class="dc-section-head"><h3>${t('dc.tab.topology')}</h3><p class="muted">${t('dc.topology_empty')}</p></div>`;
      return;
    }
    const mapOptions = maps.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
    el.innerHTML = `<div class="dc-section-head"><h3>${t('dc.topology_title', { name: dc.name })}</h3>
      <p class="muted">${t('dc.portal.topology_desc')}</p></div>
      ${maps.length > 1 ? `<div class="toolbar"><select id="dc-map-selector">${mapOptions}</select></div>` : ''}
      <div id="dc-topology-graph"></div>`;
    const renderSelected = (map) => setTimeout(() => renderDcTopology(map.topology), 50);
    renderSelected(maps[0]);
    if (maps.length > 1) {
      document.getElementById('dc-map-selector').onchange = (e) => {
        const map = maps.find(m => String(m.id) === e.target.value);
        if (map) renderSelected(map);
      };
    }
    return;
  }

  if (tab === 'alerts') {
    const alerts = currentDcOverview.alerts;
    const dash = t('common.dash');
    el.innerHTML = `<h3>${t('dc.tab.alerts')}</h3><table><thead><tr><th>${t('common.title')}</th><th>${t('common.severity')}</th><th>${t('common.status')}</th><th>${t('common.source')}</th><th>${t('common.date')}</th><th>${t('common.action')}</th></tr></thead><tbody>
      ${alerts.length ? alerts.map(a => `<tr>
        <td>${a.title}</td><td class="severity-${a.severity}">${a.severity}</td><td>${a.status}</td>
        <td>${a.source}</td><td>${localeDate(a.created_at)}</td>
        <td>${a.status === 'open' && hasPerm('manage_alerts') ? `<button class="btn-sm" onclick="ackAlert(${a.id});openDatacenterDetail(${selectedDatacenterId})">${t('alerts.ack')}</button>` : dash}</td>
      </tr>`).join('') : `<tr><td colspan="6" style="text-align:center;color:var(--muted)">${t('alerts.no_open')}</td></tr>`}
    </tbody></table>`;
    return;
  }

  if (tab === 'reports') {
    el.innerHTML = `<div class="dc-section-head"><h3>${t('dc.reports_title', { name: dc.name })}</h3>
      <p class="muted">${t('dc.reports_desc')}</p></div>
      <div class="dc-reports-grid">
        <div class="dc-report-card">
          <h4>📄 ${t('dc.portal.report_pdf')}</h4>
          <p>${t('dc.portal.report_pdf_desc')}</p>
          <button id="dc-download-report">${t('dc.download_report')}</button>
        </div>
        <div class="dc-report-card">
          <h4>📊 ${t('dc.portal.report_summary')}</h4>
          <ul class="dc-report-summary">
            <li>${t('stats.switches')}: <strong>${s.switches}</strong></li>
            <li>${t('stats.servers_short')}: <strong>${s.servers}</strong></li>
            <li>${t('stats.storage_short')}: <strong>${s.storage}</strong></li>
            <li>${t('stats.alerts')}: <strong>${s.open_alerts}</strong></li>
            <li>${t('stats.sensors')}: <strong>${s.total_sensors}</strong></li>
          </ul>
        </div>
      </div>`;
    document.getElementById('dc-download-report')?.addEventListener('click', () => downloadDcReport(selectedDatacenterId));
  }
}

function switchDcTab(tab) {
  document.querySelectorAll('.dc-tab').forEach(btn => btn.classList.toggle('active', btn.dataset.dcTab === tab));
  renderDcTab(tab);
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
document.getElementById('dc-refresh-btn')?.addEventListener('click', refreshDatacenterPortal);
document.getElementById('dc-poll-all-btn')?.addEventListener('click', pollDcAssets);
document.getElementById('dc-download-report-hero')?.addEventListener('click', () => {
  if (selectedDatacenterId) downloadDcReport(selectedDatacenterId);
});
window.addEventListener('hashchange', () => {
  const m = location.hash.match(/^#dc\/(\d+)$/);
  if (m && token) openDatacenterDetail(Number(m[1]));
  else if (!location.hash.startsWith('#dc/') && selectedDatacenterId) loadDashboard();
});
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
      <td>${d.last_seen ? localeDate(d.last_seen) : t('common.dash')}</td>
      <td><button class="btn-sm" onclick="pollDevice(${d.id})">${t('common.poll')}</button></td>
    </tr>
  `).join('') || `<tr><td colspan="6" style="text-align:center;color:var(--muted)">${t('devices.no_devices')}</td></tr>`;
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
    const poll = confirm(t('devices.added_poll'));
    if (poll) await pollDevice(device.id);
  } catch (err) {
    document.getElementById('add-device-msg').textContent = err.message;
  }
});

document.getElementById('network-discover-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const statusEl = document.getElementById('discover-status');
  const resultsEl = document.getElementById('discover-results');
  statusEl.textContent = t('devices.scanning');
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
  else { statusEl.textContent = t('devices.cidr_required'); return; }

  try {
    const result = await api('/devices/discover', { method: 'POST', body });
    statusEl.textContent = t('devices.scan_result', { scanned: result.scanned, found: result.found });
    if (result.devices.length === 0) {
      resultsEl.innerHTML = `<p class="muted">${t('devices.scan_none')}</p>`;
      return;
    }
    resultsEl.innerHTML = `
      <table class="discover-table">
        <thead><tr><th></th><th>${t('common.ip')}</th><th>${t('devices.hostname')}</th><th>${t('common.vendor')}</th><th>${t('common.desc')}</th></tr></thead>
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
        <button id="import-selected">${t('devices.import_selected', { count: result.found })}</button>
      </div>`;
    document.getElementById('import-selected').addEventListener('click', importSelectedDevices);
  } catch (err) {
    statusEl.textContent = t('devices.scan_error', { message: err.message });
  }
});

async function importSelectedDevices() {
  const ips = [...document.querySelectorAll('.disc-check:checked')].map(c => c.dataset.ip);
  if (!ips.length) return alert(t('devices.select_one'));
  const dcId = parseInt(document.getElementById('disc-dc').value);
  const community = document.getElementById('disc-community').value;
  const port = parseInt(document.getElementById('disc-port').value) || 161;
  try {
    const result = await api('/devices/import-discovered', {
      method: 'POST',
      body: { datacenter_id: dcId, community, port, ips, poll_after_import: true },
    });
    alert(t('devices.imported', { imported: result.imported, skipped: result.skipped }));
    document.getElementById('discover-form').classList.add('hidden');
    loadDevices();
  } catch (e) { alert(e.message); }
}

document.getElementById('poll-all-devices').addEventListener('click', async () => {
  try {
    const result = await api('/devices/poll-all', { method: 'POST' });
    alert(t('devices.poll_result', { total: result.total, online: result.online, offline: result.offline }));
    loadDevices();
  } catch (e) { alert(e.message); }
});

async function pollDevice(id) {
  try {
    const result = await api(`/devices/${id}/poll`, { method: 'POST' });
    alert(result.success ? t('devices.poll_ok', { protocol: result.protocol }) : t('devices.poll_fail', { error: result.error }));
    loadDevices();
  } catch (e) { alert(e.message); }
}

async function loadNetworkMap() {
  const maps = await api('/network-maps');
  const selector = document.getElementById('map-selector');
  selector.innerHTML = maps.map(m => `<option value="${m.id}">${m.name}</option>`).join('')
    || `<option value="">${t('common.dash')}</option>`;

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
      <td>${a.source || t('common.dash')}</td>
      <td>${localeDate(a.created_at)}</td>
      <td>
        ${a.status === 'open' && hasPerm('manage_alerts') ? `<button class="btn-sm" onclick="ackAlert(${a.id})">${t('alerts.ack')}</button> ` : ''}
        ${a.status !== 'resolved' && hasPerm('manage_alerts') ? `<button class="btn-sm" onclick="resolveAlert(${a.id})">${t('alerts.resolve')}</button>` : t('common.dash')}
      </td>
    </tr>
  `).join('') || `<tr><td colspan="6" style="text-align:center;color:var(--muted)">${t('alerts.no_alerts')}</td></tr>`;
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
  if (!dcId) return alert(t('reports.select_dc'));
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
    el.innerHTML = `<h4>${t('servers.guide_title')}</h4><ul>${guide.protocols.map(p =>
      `<li>${t('servers.guide_item', { protocol: p.protocol.toUpperCase(), port: p.port, description: p.description })}<br>${t('servers.guide_fields', { fields: p.fields.join(', ') })}</li>`
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
      <td>${s.last_seen ? localeDate(s.last_seen) : t('common.dash')}</td>
      <td><button class="btn-sm" onclick="pollServer(${s.id})">${t('common.poll')}</button>
          <button class="btn-sm btn-secondary" onclick="showServerCreds(${s.id})">${t('servers.creds')}</button></td>
    </tr>`).join('') || `<tr><td colspan="7" style="text-align:center;color:var(--muted)">${t('servers.no_servers')}</td></tr>`;
}

async function pollServer(id) {
  try {
    const r = await api(`/servers/${id}/poll`, { method: 'POST' });
    alert(r.success ? t('servers.poll_ok', { protocol: r.protocol, metrics: r.metrics || 0 }) : t('servers.poll_fail', { error: r.error }));
    loadServers();
  } catch (e) { alert(e.message); }
}

async function showServerCreds(id) {
  const creds = await api(`/servers/${id}/credentials`);
  alert(creds.map(c => t('servers.creds_line', {
    protocol: c.protocol,
    user: c.username || '-',
    port: c.port || t('common.default'),
    pwd: c.has_password ? '✓' : '✗',
  })).join('\n') || t('servers.no_creds'));
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
    if (confirm(t('servers.added_poll'))) pollServer(s.id);
  } catch (err) { alert(err.message); }
});

document.getElementById('poll-all-servers').addEventListener('click', async () => {
  const r = await api('/servers/poll-all', { method: 'POST' });
  alert(t('servers.poll_result', { online: r.online, total: r.total }));
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
    el.innerHTML = `<h4>${t('storage.guide_title')}</h4><ul>${guide.protocols.map(p =>
      `<li>${t('servers.guide_item', { protocol: p.protocol.toUpperCase(), port: p.port, description: p.description })}<br>${t('servers.guide_fields', { fields: p.fields.join(', ') })}</li>`
    ).join('')}</ul>`;
  }
});

async function loadStorage() {
  await populateDatacenterSelects();
  const items = await api('/storage');
  document.querySelector('#storage-table tbody').innerHTML = items.map(s => {
    const dash = t('common.dash');
    const usage = s.total_capacity_tb && s.used_capacity_tb
      ? `${((s.used_capacity_tb / s.total_capacity_tb) * 100).toFixed(1)}%` : dash;
    const cap = s.total_capacity_tb ? `${s.used_capacity_tb || 0}/${s.total_capacity_tb} TB` : dash;
    return `<tr>
      <td>${s.name}</td><td>${s.ip_address}</td><td>${s.vendor}${s.model ? ' / ' + s.model : ''}</td><td>${cap}</td><td>${usage}</td>
      <td class="status-${s.status}">${s.status}</td>
      <td><button class="btn-sm" onclick="pollStorage(${s.id})">${t('common.poll')}</button>
          <button class="btn-sm btn-secondary" onclick="showStorageCreds(${s.id})">${t('servers.creds')}</button></td>
    </tr>`;
  }).join('') || `<tr><td colspan="7" style="text-align:center;color:var(--muted)">${t('storage.no_systems')}</td></tr>`;
}

async function pollStorage(id) {
  try {
    const r = await api(`/storage/${id}/poll`, { method: 'POST' });
    alert(r.success ? t('storage.poll_ok', { pct: r.capacity_usage_pct || '?' }) : t('storage.poll_fail', { error: r.error }));
    loadStorage();
  } catch (e) { alert(e.message); }
}

async function showStorageCreds(id) {
  const creds = await api(`/storage/${id}/credentials`);
  alert(creds.map(c => t('storage.creds_line', {
    protocol: c.protocol,
    port: c.port || t('common.default'),
    community: c.has_community ? '✓' : '✗',
    token: c.has_token ? '✓' : '✗',
  })).join('\n') || t('servers.no_creds'));
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
    if (confirm(t('servers.added_poll'))) pollStorage(s.id);
  } catch (err) { alert(err.message); }
});

document.getElementById('poll-all-storage').addEventListener('click', async () => {
  const r = await api('/storage/poll-all', { method: 'POST' });
  alert(t('storage.poll_result', { online: r.online, total: r.total }));
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
  document.getElementById('user-form-title').textContent = t('users.add_title');
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
      <td>${roleLabel(u.role)}</td>
      <td>${(u.permissions || []).slice(0, 3).map(p => `<span class="badge-perm">${p}</span>`).join('')}${(u.permissions||[]).length > 3 ? ' +' + ((u.permissions||[]).length-3) : ''}</td>
      <td class="${u.is_active ? 'badge-active' : 'badge-inactive'}">${u.is_active ? t('users.active') : t('users.inactive')}</td>
      <td>
        <button class="btn-sm" onclick="editUser(${u.id})">${t('users.edit')}</button>
        ${u.id !== currentUser?.id ? `<button class="btn-sm btn-secondary" onclick="deleteUser(${u.id})">${t('users.delete')}</button>` : ''}
      </td>
    </tr>`).join('') || `<tr><td colspan="6" style="text-align:center;color:var(--muted)">${t('users.no_users')}</td></tr>`;
}

async function editUser(id) {
  const u = await api(`/users/${id}`);
  document.getElementById('user-form-title').textContent = t('users.edit_title');
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
  if (!confirm(t('users.confirm_delete'))) return;
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
    dcSelect.innerHTML = `<option value="">${t('sensors.all_dcs')}</option>` +
      dcs.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
    if (dcId) dcSelect.value = dcId;
  }

  document.getElementById('sensor-summary-bar').innerHTML = `
    <div class="chip"><span class="sensor-dot up"></span>${t('sensors.summary_up', { count: summary.up || 0 })}</div>
    <div class="chip"><span class="sensor-dot warning"></span>${t('sensors.summary_warning', { count: summary.warning || 0 })}</div>
    <div class="chip"><span class="sensor-dot down"></span>${t('sensors.summary_down', { count: summary.down || 0 })}</div>
    <div class="chip"><span class="sensor-dot paused"></span>${t('sensors.summary_paused', { count: summary.paused || 0 })}</div>
    <div class="chip"><span class="sensor-dot unknown"></span>${t('sensors.summary_unknown', { count: summary.unknown || 0 })}</div>
    <div class="chip">${t('sensors.summary_total', { count: summary.total || 0 })}</div>
  `;

  const tbody = document.querySelector('#sensors-table tbody');
  tbody.innerHTML = sensors.map(s => {
    const dash = t('common.dash');
    const val = s.last_value != null ? `${s.last_value}${s.unit || ''}` : dash;
    return `<tr>
      <td><span class="sensor-dot ${s.last_status}" title="${s.status_label}"></span></td>
      <td>${s.name}</td>
      <td>${s.asset_name || dash}</td>
      <td>${assetTypeLabel(s.asset_type) || s.asset_type}</td>
      <td><strong>${val}</strong></td>
      <td>${s.warning_limit ?? dash}</td>
      <td>${s.error_limit ?? dash}</td>
      <td class="sensor-status-${s.last_status}">${s.status_label}</td>
      <td>${s.last_check_at ? localeDate(s.last_check_at) : dash}</td>
      <td><button class="btn-sm" onclick="openSensorDetail(${s.id})">${t('sensors.detail')}</button></td>
    </tr>`;
  }).join('') || `<tr><td colspan="10" style="text-align:center;color:var(--muted)">${t('sensors.no_sensors')}</td></tr>`;
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
    chart.innerHTML = `<p class="muted">${t('sensors.no_history')}</p>`;
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
    alert(t('sensors.seeded', { count: r.created }));
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
    document.getElementById('excel-status').textContent = t('excel.only_xlsx');
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
    <div class="stat-card"><div class="value">${s.total || 0}</div><div class="label">${t('stats.total_assets')}</div></div>
    <div class="stat-card"><div class="value">${s.devices || 0}</div><div class="label">${t('stats.network_devices')}</div></div>
    <div class="stat-card"><div class="value">${s.servers || 0}</div><div class="label">${t('stats.servers_short')}</div></div>
    <div class="stat-card"><div class="value">${s.storage || 0}</div><div class="label">${t('stats.storage_short')}</div></div>
    <div class="stat-card"><div class="value">${s.links || 0}</div><div class="label">${t('stats.links')}</div></div>
    <div class="stat-card"><div class="value">${s.datacenters || 0}</div><div class="label">${t('stats.datacenters')}</div></div>
  `;
  const errBox = document.getElementById('excel-errors');
  if (data.errors?.length) {
    errBox.classList.remove('hidden');
    errBox.innerHTML = `<strong>${t('excel.warnings')}</strong><ul>` + data.errors.map(e => `<li>${e}</li>`).join('') + '</ul>';
  } else {
    errBox.classList.add('hidden');
    errBox.innerHTML = '';
  }
  document.getElementById('excel-dc-list').innerHTML = (data.datacenters || []).length
    ? data.datacenters.map(d => `<span class="tag">${d}</span>`).join(' ')
    : `<span class="muted">${t('excel.none')}</span>`;
  document.querySelector('#excel-assets-table tbody').innerHTML = (data.assets || []).map(a => `
    <tr>
      <td>${a.row}</td><td>${a.datacenter}</td><td>${a.asset_type}</td>
      <td>${a.name}</td><td>${a.ip_address}</td><td>${a.vendor || t('common.dash')}</td><td>${a.protocol || t('common.dash')}</td>
    </tr>
  `).join('') || `<tr><td colspan="7" style="text-align:center;color:var(--muted)">${t('common.no_assets')}</td></tr>`;
  document.querySelector('#excel-links-table tbody').innerHTML = (data.links || []).map(l => `
    <tr>
      <td>${l.row}</td><td>${l.datacenter}</td>
      <td>${l.from_name || l.from || t('common.dash')}</td><td>${l.to_name || l.to || t('common.dash')}</td><td>${l.label || t('common.dash')}</td>
    </tr>
  `).join('') || `<tr><td colspan="5" style="text-align:center;color:var(--muted)">${t('excel.no_links')}</td></tr>`;
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
  statusEl.textContent = t('excel.parsing');
  try {
    const form = new FormData();
    form.append('file', excelSelectedFile);
    const data = await api('/import/excel/preview', { method: 'POST', body: form });
    renderExcelPreview(data);
    statusEl.textContent = t('excel.parsed');
  } catch (err) {
    statusEl.textContent = err.message;
  }
});

document.getElementById('excel-apply-btn')?.addEventListener('click', async () => {
  if (!excelSelectedFile) return;
  if (!confirm(t('excel.confirm_import'))) return;
  const statusEl = document.getElementById('excel-status');
  statusEl.textContent = t('excel.importing');
  try {
    const form = new FormData();
    form.append('file', excelSelectedFile);
    const skip = document.getElementById('excel-skip-existing').checked;
    const data = await api(`/import/excel/apply?skip_existing=${skip}`, { method: 'POST', body: form });
    statusEl.textContent = t('excel.imported', {
      imported: data.imported,
      skipped: data.skipped,
      datacenters: data.datacenters,
      maps: data.maps_updated,
    });
    if (data.errors?.length) {
      statusEl.textContent += t('excel.imported_warnings', { warnings: data.errors.join('; ') });
    }
    await loadDashboard();
  } catch (err) {
    statusEl.textContent = err.message;
  }
});

window.openDatacenterDetail = openDatacenterDetail;
window.switchDcTab = switchDcTab;
window.ackAlert = ackAlert;
window.resolveAlert = resolveAlert;
window.downloadDcReport = downloadDcReport;

if (token) {
  initApp().catch(() => logout());
} else {
  showPanel('login');
}
