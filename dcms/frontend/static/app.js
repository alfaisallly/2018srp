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

function canManageIntegrations() {
  return hasPerm('manage_integrations') || currentUser?.role === 'admin';
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
  document.getElementById('show-add-prefix')?.classList.toggle('hidden', !hasPerm('manage_ipam'));
  document.getElementById('show-add-integration')?.classList.toggle('hidden', !canManageIntegrations());
  document.getElementById('sync-all-integrations')?.classList.toggle('hidden', !canManageIntegrations());
  document.getElementById('run-all-backups')?.classList.toggle('hidden', !hasPerm('manage_devices'));
  document.getElementById('theme-fab')?.classList.toggle('hidden', !currentUser);
  document.getElementById('open-appearance')?.classList.toggle('hidden', !currentUser);
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
    if (panel === 'network-control') loadNetworkControl();
    if (panel === 'sensors') loadSensors();
    if (panel === 'alerts') loadAlerts();
    if (panel === 'reports') loadReportSelector();
    if (panel === 'users') loadUsers();
    if (panel === 'dashboard') loadDashboard();
    if (panel === 'ipam') loadIpam();
    if (panel === 'backups') loadBackups();
    if (panel === 'integrations') loadIntegrations();
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
  else if (activePanel === 'network-control') loadNetworkControl();
  else if (activePanel === 'reports') loadReportSelector();
  else if (activePanel === 'users') loadUsers();
  else if (activePanel === 'ipam') loadIpam();
  else if (activePanel === 'backups') loadBackups();
  else if (activePanel === 'integrations') loadIntegrations();
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

  await loadCapabilities();

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

let netctrlNetwork = null;
let netctrlTemplates = [];
let selectedNetctrlTemplate = null;

const linkTypeLabels = {
  fiber: () => t('netctrl.link.fiber'),
  copper: () => t('netctrl.link.copper'),
  wireless: () => t('netctrl.link.wireless'),
  backup: () => t('netctrl.link.backup'),
  logical: () => t('netctrl.link.logical'),
};

async function loadNetworkControl() {
  const dcs = await api('/datacenters');
  const dcFilter = document.getElementById('netctrl-dc-filter');
  const prev = dcFilter.value;
  dcFilter.innerHTML = `<option value="">${t('common.all_dcs')}</option>` +
    dcs.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
  if (prev) dcFilter.value = prev;

  const dcId = dcFilter.value ? Number(dcFilter.value) : null;
  const q = dcId ? `?datacenter_id=${dcId}` : '';

  const [overview, devices, vlans, links, firewall, branches, templates] = await Promise.all([
    api(`/network/overview${q}`),
    api(`/network/devices${q}`),
    api(`/network/vlans${q}`),
    api(`/network/links${q}`),
    api(`/network/firewall${q}`),
    api(`/network/branches${q}`),
    api('/network/config-templates'),
  ]);

  netctrlTemplates = templates;
  renderNetctrlSummary(overview);
  populateNetctrlDeviceFilter(devices);
  renderNetctrlPorts(devices, dcId);
  renderNetctrlVlans(vlans);
  renderNetctrlFirewall(firewall);
  renderNetctrlBranches(branches);
  renderNetctrlTemplates(templates);
  renderNetctrlSwitches(devices);

  if (dcId) {
    const topo = await api(`/network/topology/${dcId}`);
    renderNetctrlTopology(topo);
  } else if (dcs.length) {
    const topo = await api(`/network/topology/${dcs[0].id}`);
    renderNetctrlTopology(topo);
  }
}

function renderNetctrlSummary(o) {
  document.getElementById('netctrl-summary').innerHTML = `
    <div class="stat-card"><strong>${o.ports_total}</strong><span>${t('netctrl.stat.ports')}</span></div>
    <div class="stat-card up"><strong>${o.ports_up}</strong><span>${t('netctrl.stat.ports_up')}</span></div>
    <div class="stat-card down"><strong>${o.ports_down}</strong><span>${t('netctrl.stat.ports_down')}</span></div>
    <div class="stat-card"><strong>${o.vlans_total}</strong><span>${t('netctrl.stat.vlans')}</span></div>
    <div class="stat-card"><strong>${o.links_total}</strong><span>${t('netctrl.stat.links')}</span></div>
    <div class="stat-card"><strong>${o.firewall_rules_total}</strong><span>${t('netctrl.stat.firewall')}</span></div>
    <div class="stat-card"><strong>${o.branch_sites_total}</strong><span>${t('netctrl.stat.branches')}</span></div>
  `;
}

function populateNetctrlDeviceFilter(devices) {
  const sel = document.getElementById('netctrl-device-filter');
  const prev = sel.value;
  sel.innerHTML = `<option value="">${t('netctrl.all_devices')}</option>` +
    devices.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
  if (prev) sel.value = prev;
}

async function renderNetctrlPorts(devices, dcId) {
  const deviceFilter = document.getElementById('netctrl-device-filter').value;
  const allPorts = [];
  const targetDevices = deviceFilter ? devices.filter(d => d.id == deviceFilter) : devices;
  for (const d of targetDevices) {
    const ports = await api(`/network/devices/${d.id}/ports`);
    ports.forEach(p => allPorts.push({ ...p, device_name: d.name, device_id: d.id }));
  }
  const tbody = document.querySelector('#netctrl-ports-table tbody');
  tbody.innerHTML = allPorts.map(p => {
    const vlanInfo = p.vlan_mode === 'access' ? (p.access_vlan || '—') : `Trunk: ${(p.trunk_vlans || []).join(',')}`;
    let conn = '—';
    if (p.connected_device_name) {
      conn = `${p.connected_device_name}:${p.connected_port_name || '?'}`;
      if (p.link_type) conn += ` (${linkTypeLabels[p.link_type]?.() || p.link_type})`;
    }
    return `<tr class="netctrl-port-row">
      <td><button type="button" class="link-btn" onclick="openSwitchDetail(${p.device_id})">${p.device_name || '—'}</button></td>
      <td><code>${p.name}</code></td>
      <td class="status-${p.oper_status}">${p.oper_status}</td>
      <td>${p.speed_mbps ? p.speed_mbps + ' Mbps' : '—'}</td>
      <td>${vlanInfo}</td>
      <td>${conn}</td>
      <td>${(p.services || []).join(', ') || '—'}</td>
      <td>${p.description || '—'}</td>
    </tr>`;
  }).join('') || `<tr><td colspan="8" style="text-align:center;color:var(--muted)">${t('netctrl.no_ports')}</td></tr>`;
}

function renderNetctrlVlans(vlans) {
  const tbody = document.querySelector('#netctrl-vlans-table tbody');
  tbody.innerHTML = vlans.map(v => `<tr>
    <td>${v.vlan_id}</td><td>${v.name}</td><td>${v.device_name || '—'}</td>
    <td>${v.subnet || '—'}</td><td>${v.gateway || '—'}</td><td>${v.status}</td>
  </tr>`).join('') || `<tr><td colspan="6" style="text-align:center;color:var(--muted)">${t('netctrl.no_vlans')}</td></tr>`;
}

function renderNetctrlFirewall(rules) {
  const tbody = document.querySelector('#netctrl-firewall-table tbody');
  tbody.innerHTML = rules.map(r => `<tr>
    <td>${r.device_name}</td><td>${r.name}</td>
    <td class="fw-${r.action}">${r.action}</td>
    <td>${r.source || '—'}</td><td>${r.destination || '—'}</td>
    <td>${r.service || '—'}</td>
    <td>${r.zone_in || '?'} → ${r.zone_out || '?'}</td>
  </tr>`).join('') || `<tr><td colspan="7" style="text-align:center;color:var(--muted)">${t('netctrl.no_firewall')}</td></tr>`;
}

function renderNetctrlBranches(branches) {
  const tbody = document.querySelector('#netctrl-branches-table tbody');
  tbody.innerHTML = branches.map(b => {
    const primary = b.primary_device_name ? `${b.primary_device_name}:${b.primary_port || '?'} (${linkTypeLabels[b.primary_link_type]?.() || b.primary_link_type})` : '—';
    let backup = '—';
    if (b.backup_enabled) {
      const bt = linkTypeLabels[b.backup_link_type]?.() || t('netctrl.link.wireless');
      backup = b.backup_device_name ? `${b.backup_device_name}:${b.backup_port || b.backup_wireless_ssid || '?'} (${bt})` : bt;
    }
    return `<tr><td>${b.name}</td><td>${b.location || '—'}</td><td>${primary}</td><td>${backup}</td><td>${b.status}</td></tr>`;
  }).join('') || `<tr><td colspan="5" style="text-align:center;color:var(--muted)">${t('netctrl.no_branches')}</td></tr>`;
}

function renderNetctrlTopology(topo) {
  const container = document.getElementById('netctrl-topology-graph');
  if (!container || !topo?.nodes?.length) return;
  const data = { nodes: new vis.DataSet(topo.nodes), edges: new vis.DataSet(topo.edges || []) };
  const options = {
    layout: { improvedLayout: true },
    physics: { stabilization: { iterations: 200 } },
    nodes: { font: { color: '#f1f5f9', size: 12 }, shapeProperties: { borderRadius: 4 } },
    edges: { smooth: { type: 'continuous' }, font: { size: 9, align: 'middle', color: '#94a3b8' } },
    interaction: { hover: true, tooltipDelay: 150 },
  };
  if (netctrlNetwork) netctrlNetwork.destroy();
  netctrlNetwork = new vis.Network(container, data, options);
  netctrlNetwork.on('click', (params) => {
    if (!params.nodes.length) return;
    const nodeId = params.nodes[0];
    const match = String(nodeId).match(/^dev-(\d+)$/);
    if (match) openSwitchDetail(Number(match[1]));
  });
}

function renderNetctrlSwitches(devices) {
  const grid = document.getElementById('netctrl-switches-grid');
  if (!grid) return;
  const networkDevices = devices.filter(d => ['switch', 'router', 'firewall'].includes(d.device_type));
  grid.innerHTML = networkDevices.map(d => `
    <div class="switch-card" onclick="openSwitchDetail(${d.id})">
      <div class="switch-card-header">
        <div>
          <div class="switch-card-vendor ${d.vendor}">${vendorLabel(d.vendor)} · ${deviceTypeLabel(d.device_type)}</div>
          <strong>${d.name}</strong>
          <div class="muted" style="font-size:0.85rem">${d.ip_address}</div>
        </div>
        <span class="status-badge status-${d.status}">${d.status}</span>
      </div>
      <div class="switch-card-stats">
        <span>${t('netctrl.click_details')}</span>
      </div>
    </div>
  `).join('') || `<p class="muted">${t('netctrl.no_switches')}</p>`;
}

let switchLocalNetwork = null;
let currentSwitchDetail = null;
let selectedSwitchPort = null;

async function openSwitchDetail(deviceId) {
  if (!deviceId) return;
  try {
    const detail = await api(`/network/devices/${deviceId}/detail`);
    currentSwitchDetail = detail;
    renderSwitchDetailModal(detail);
    document.getElementById('switch-detail-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  } catch (e) { alert(e.message); }
}

function closeSwitchDetail() {
  document.getElementById('switch-detail-modal').classList.add('hidden');
  document.body.style.overflow = '';
  if (switchLocalNetwork) { switchLocalNetwork.destroy(); switchLocalNetwork = null; }
  currentSwitchDetail = null;
  selectedSwitchPort = null;
}

function renderSwitchDetailModal(d) {
  const dev = d.device;
  const cap = d.capacity;
  document.getElementById('switch-detail-title').textContent = dev.name;
  document.getElementById('switch-detail-subtitle').textContent =
    `${vendorLabel(dev.vendor)} · ${deviceTypeLabel(dev.device_type)} · ${dev.ip_address} · ${dev.datacenter_name || ''}`;

  document.getElementById('switch-detail-insights').innerHTML =
    (d.insights || []).map(i => `<div class="switch-insight">${i}</div>`).join('');

  document.getElementById('switch-capacity-bars').innerHTML = `
    <div class="capacity-card">
      <label>${t('netctrl.cap.total_bw')}</label>
      <strong>${cap.total_capacity_mbps} Mbps</strong>
      <div class="capacity-bar-wrap"><div class="capacity-bar bw" style="width:100%"></div></div>
      <small class="muted">${t('netctrl.cap.min')}: ${cap.min_port_mbps} · ${t('netctrl.cap.max')}: ${cap.max_port_mbps} Mbps</small>
    </div>
    <div class="capacity-card">
      <label>${t('netctrl.cap.used_bw')}</label>
      <strong>${cap.used_capacity_mbps} / ${cap.active_capacity_mbps} Mbps</strong>
      <div class="capacity-bar-wrap"><div class="capacity-bar bw" style="width:${Math.min(cap.bandwidth_utilization_pct, 100)}%"></div></div>
      <small class="muted">${cap.bandwidth_utilization_pct}% · ${t('netctrl.cap.available')}: ${cap.available_capacity_mbps} Mbps</small>
    </div>
    <div class="capacity-card">
      <label>${t('netctrl.cap.packets')}</label>
      <strong>${cap.total_packets_per_sec.toLocaleString()} pps</strong>
      <div class="capacity-bar-wrap"><div class="capacity-bar pps" style="width:${Math.min(cap.packets_utilization_pct, 100)}%"></div></div>
      <small class="muted">${t('netctrl.cap.max_pps')}: ${cap.max_packets_per_sec.toLocaleString()} · ${cap.packets_utilization_pct}%</small>
    </div>
    <div class="capacity-card">
      <label>${t('netctrl.cap.ports')}</label>
      <strong>${cap.ports_up} / ${cap.total_ports}</strong>
      <small class="muted">${t('netctrl.stat.ports_up')} · MTU ${cap.mtu}</small>
    </div>
  `;

  document.getElementById('switch-tab-ports').innerHTML = `
    <table>
      <thead><tr>
        <th>${t('netctrl.port')}</th><th>${t('common.status')}</th><th>${t('netctrl.speed')}</th>
        <th>${t('netctrl.vlan')}</th><th>${t('netctrl.connection')}</th><th>${t('netctrl.services')}</th>
        <th>${t('netctrl.cap.util')}</th><th>${t('common.desc')}</th>
      </tr></thead>
      <tbody>${d.ports.map(p => {
        const peer = p.peer ? `${p.peer.device_name}:${p.peer.port_name || '?'}` : '—';
        const util = p.settings?.utilization_pct ?? 0;
        return `<tr class="switch-port-row" onclick="showPortDetail(${p.id})" style="cursor:pointer">
          <td><code>${p.name}</code></td>
          <td class="status-${p.oper_status}">${p.oper_status}</td>
          <td>${p.speed_mbps} Mbps</td>
          <td>${p.vlan_info.summary}</td>
          <td>${peer}${p.link_type_label ? ` (${p.link_type_label})` : ''}</td>
          <td>${(p.services || []).join(', ') || '—'}</td>
          <td>${util}% · ${p.settings?.avg_pps?.toLocaleString() || 0} pps</td>
          <td>${p.description || '—'}</td>
        </tr>`;
      }).join('')}</tbody>
    </table>
    <div id="switch-port-detail-pop"></div>
  `;

  document.getElementById('switch-tab-grid').innerHTML = `
    <div class="port-grid">${d.ports.map(p => {
      const util = p.settings?.utilization_pct ?? 0;
      const peer = p.peer ? `→ ${p.peer.device_name}:${p.peer.port_name || '?'}` : '';
      return `<div class="port-tile ${p.oper_status}" onclick="showPortDetail(${p.id})">
        <div class="port-tile-name">${p.name}</div>
        <div class="port-tile-status status-${p.oper_status}">${p.oper_status} · ${p.speed_mbps}M</div>
        <div class="port-tile-peer">${p.vlan_info.summary}</div>
        ${peer ? `<div class="port-tile-peer">${peer}</div>` : ''}
        <div class="port-tile-util"><div class="port-tile-util-bar" style="width:${util}%"></div></div>
      </div>`;
    }).join('')}</div>
    <div id="switch-port-detail-pop-grid"></div>
  `;

  document.getElementById('switch-tab-vlans').innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>${t('common.name')}</th><th>${t('netctrl.subnet')}</th><th>Gateway</th><th>${t('netctrl.swtab.ports_on_vlan')}</th></tr></thead>
      <tbody>${d.vlans.map(v => `<tr>
        <td>${v.vlan_id}</td><td>${v.name}</td><td>${v.subnet || '—'}</td><td>${v.gateway || '—'}</td>
        <td>${(v.ports || []).join(', ') || '—'} (${v.port_count})</td>
      </tr>`).join('')}</tbody>
    </table>
  `;

  document.getElementById('switch-tab-peers').innerHTML = d.peers.length ? d.peers.map(peer => `
    <div class="card" style="margin-bottom:0.75rem;padding:1rem">
      <div class="toolbar" style="margin-bottom:0.5rem">
        <strong>${peer.name}</strong>
        <button type="button" class="btn-sm link-btn" onclick="openSwitchDetail(${peer.device_id})">${t('netctrl.open_peer')}</button>
      </div>
      <div class="muted">${peer.ip_address} · ${deviceTypeLabel(peer.device_type)} · ${vendorLabel(peer.vendor)}</div>
      <table style="margin-top:0.5rem"><thead><tr>
        <th>${t('netctrl.local_port')}</th><th>${t('netctrl.remote_port')}</th><th>${t('netctrl.connection')}</th>
      </tr></thead><tbody>${peer.ports.map(p => `<tr>
        <td><code>${p.local}</code></td><td><code>${p.remote || '—'}</code></td><td>${p.link_type || '—'}</td>
      </tr>`).join('')}</tbody></table>
    </div>
  `).join('') : `<p class="muted">${t('netctrl.no_peers')}</p>`;

  document.getElementById('switch-tab-firewall').innerHTML = d.firewall_rules.length ? `
    <table><thead><tr>
      <th>${t('common.device')}</th><th>${t('common.name')}</th><th>${t('netctrl.action')}</th>
      <th>${t('netctrl.source')}</th><th>${t('netctrl.destination')}</th><th>${t('netctrl.service')}</th><th>${t('netctrl.scope')}</th>
    </tr></thead><tbody>${d.firewall_rules.map(r => `<tr>
      <td>${r.device_name}</td><td>${r.name}</td><td class="fw-${r.action}">${r.action}</td>
      <td>${r.source || '—'}</td><td>${r.destination || '—'}</td><td>${r.service || '—'}</td>
      <td>${r.scope === 'local' ? t('netctrl.scope_local') : t('netctrl.scope_related')}</td>
    </tr>`).join('')}</tbody></table>
  ` : `<p class="muted">${t('netctrl.no_firewall')}</p>`;

  activateSwitchDetailTab('ports');
  renderSwitchLocalTopology(d.local_topology);
}

function showPortDetail(portId) {
  if (!currentSwitchDetail) return;
  const p = currentSwitchDetail.ports.find(x => x.id === portId);
  if (!p) return;
  selectedSwitchPort = p;
  const html = `
    <div class="port-detail-pop">
      <h4>${p.name} — ${p.description || t('netctrl.port')}</h4>
      <div class="port-detail-grid">
        <div><span>${t('common.status')}</span>${p.oper_status} (${p.admin_status})</div>
        <div><span>${t('netctrl.speed')}</span>${p.speed_mbps} Mbps · ${p.duplex}</div>
        <div><span>${t('netctrl.vlan')}</span>${p.vlan_info.summary}</div>
        <div><span>${t('netctrl.cap.util')}</span>${p.settings.utilization_pct}% · ${p.settings.used_mbps} Mbps</div>
        <div><span>${t('netctrl.cap.packets')}</span>${p.settings.avg_pps?.toLocaleString()} / ${p.settings.max_pps?.toLocaleString()} pps</div>
        <div><span>MTU</span>${p.settings.mtu}</div>
        <div><span>${t('netctrl.connection')}</span>${p.peer ? `${p.peer.device_name}:${p.peer.port_name} (${p.peer.ip_address})` : '—'}</div>
        <div><span>${t('netctrl.services')}</span>${(p.services || []).join(', ') || '—'}</div>
        <div><span>Storm Control</span>${p.settings.storm_control ? t('common.yes') : t('common.no')}</div>
        <div><span>PortFast</span>${p.settings.portfast ? t('common.yes') : t('common.no')}</div>
      </div>
      ${p.peer ? `<button type="button" class="btn-sm" style="margin-top:0.75rem" onclick="openSwitchDetail(${p.peer.device_id})">${t('netctrl.open_peer')}: ${p.peer.device_name}</button>` : ''}
    </div>`;
  const pop = document.getElementById('switch-port-detail-pop') || document.getElementById('switch-port-detail-pop-grid');
  if (pop) pop.innerHTML = html;
}

function renderSwitchLocalTopology(topo) {
  const container = document.getElementById('switch-local-topology');
  if (!container || !topo?.nodes?.length) return;
  if (switchLocalNetwork) switchLocalNetwork.destroy();
  switchLocalNetwork = new vis.Network(container, {
    nodes: new vis.DataSet(topo.nodes),
    edges: new vis.DataSet(topo.edges || []),
  }, {
    physics: { enabled: true, stabilization: { iterations: 100 } },
    nodes: { font: { color: '#f1f5f9', size: 11 } },
    edges: { font: { size: 8, align: 'middle' } },
  });
  switchLocalNetwork.on('click', (params) => {
    const match = String(params.nodes[0] || '').match(/^dev-(\d+)$/);
    if (match && Number(match[1]) !== currentSwitchDetail?.device?.id) openSwitchDetail(Number(match[1]));
  });
}

function activateSwitchDetailTab(name) {
  document.querySelectorAll('.switch-dtab').forEach(t => t.classList.toggle('active', t.dataset.switchTab === name));
  document.querySelectorAll('.switch-tab-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById(`switch-tab-${name}`)?.classList.remove('hidden');
}

document.querySelectorAll('.switch-dtab').forEach(tab => {
  tab.addEventListener('click', () => activateSwitchDetailTab(tab.dataset.switchTab));
});
document.getElementById('close-switch-detail')?.addEventListener('click', closeSwitchDetail);
document.getElementById('switch-modal-backdrop')?.addEventListener('click', closeSwitchDetail);

function renderNetctrlTemplates(templates) {
  const vendor = document.getElementById('netctrl-template-vendor').value;
  const filtered = vendor ? templates.filter(tpl => tpl.vendor === vendor) : templates;
  const list = document.getElementById('netctrl-templates-list');
  list.innerHTML = filtered.map(tpl => `
    <div class="template-card" data-id="${tpl.id}">
      <div class="template-vendor ${tpl.vendor}">${vendorLabel(tpl.vendor)}</div>
      <strong>${tpl.name}</strong>
      <p class="muted">${tpl.description || ''}</p>
      <div class="template-tags">${(tpl.tags || []).map(tag => `<span class="tag">${tag}</span>`).join('')}</div>
    </div>
  `).join('') || `<p class="muted">${t('netctrl.no_templates')}</p>`;

  list.querySelectorAll('.template-card').forEach(card => {
    card.addEventListener('click', () => selectNetctrlTemplate(Number(card.dataset.id)));
  });
}

function selectNetctrlTemplate(id) {
  selectedNetctrlTemplate = netctrlTemplates.find(t => t.id === id);
  if (!selectedNetctrlTemplate) return;
  document.getElementById('netctrl-template-editor').classList.remove('hidden');
  document.getElementById('netctrl-template-name').textContent = selectedNetctrlTemplate.name;
  document.getElementById('netctrl-template-desc').textContent = selectedNetctrlTemplate.description || '';
  const varsEl = document.getElementById('netctrl-template-vars');
  varsEl.innerHTML = (selectedNetctrlTemplate.variables || []).map(v => `
    <label><span>${v.label || v.name}${v.required ? ' *' : ''}</span>
      <input type="${v.type === 'number' ? 'number' : 'text'}" id="tpl-var-${v.name}" placeholder="${v.example || ''}" ${v.required ? 'required' : ''}>
    </label>
  `).join('');
  document.getElementById('netctrl-template-output').textContent = '';
}

document.querySelectorAll('.netctrl-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.netctrl-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.netctrl-tab-panel').forEach(p => p.classList.add('hidden'));
    tab.classList.add('active');
    document.getElementById(`netctrl-tab-${tab.dataset.netctrlTab}`).classList.remove('hidden');
  });
});

document.getElementById('refresh-netctrl')?.addEventListener('click', loadNetworkControl);
document.getElementById('netctrl-dc-filter')?.addEventListener('change', loadNetworkControl);
document.getElementById('netctrl-device-filter')?.addEventListener('change', async () => {
  const dcId = document.getElementById('netctrl-dc-filter').value ? Number(document.getElementById('netctrl-dc-filter').value) : null;
  const q = dcId ? `?datacenter_id=${dcId}` : '';
  const devices = await api(`/network/devices${q}`);
  renderNetctrlPorts(devices, dcId);
});
document.getElementById('netctrl-template-vendor')?.addEventListener('change', () => renderNetctrlTemplates(netctrlTemplates));

document.getElementById('netctrl-render-template')?.addEventListener('click', async () => {
  if (!selectedNetctrlTemplate) return;
  const variables = {};
  (selectedNetctrlTemplate.variables || []).forEach(v => {
    const el = document.getElementById(`tpl-var-${v.name}`);
    if (el && el.value) variables[v.name] = v.type === 'number' ? Number(el.value) : el.value;
  });
  try {
    const result = await api(`/network/config-templates/${selectedNetctrlTemplate.id}/render`, {
      method: 'POST', body: { variables },
    });
    document.getElementById('netctrl-template-output').textContent = result.config;
  } catch (e) { alert(e.message); }
});

document.getElementById('download-network-report')?.addEventListener('click', async () => {
  const dcId = document.getElementById('netctrl-dc-filter').value;
  if (!dcId) { alert(t('netctrl.select_dc_report')); return; }
  try {
    const res = await fetch(`${API}/network/reports/${dcId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `network-report-${dcId}.${blob.type.includes('pdf') ? 'pdf' : 'html'}`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) { alert(e.message); }
});

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

// --- Platform Capabilities ---
async function loadCapabilities() {
  const section = document.getElementById('capabilities-section');
  const grid = document.getElementById('capabilities-grid');
  if (!section || !grid) return;
  try {
    const data = await api('/platform/capabilities');
    section.classList.remove('hidden');
    grid.innerHTML = (data.modules || []).map(m => `
      <div class="capability-card ${m.active ? 'active' : ''}">
        <div class="capability-icon">${m.icon}</div>
        <h4>${t(m.title_key)}</h4>
        <p class="muted">${t(m.description_key)}</p>
        <span class="capability-badge ${m.active ? 'badge-active' : 'badge-ready'}">${m.active ? t('capabilities.active') : t('capabilities.ready')}</span>
      </div>
    `).join('');
  } catch {
    section.classList.add('hidden');
  }
}

// --- IPAM ---
let selectedPrefixId = null;
const ipamStatusLabel = (s) => t(`ipam.status.${s}`) === `ipam.status.${s}` ? s : t(`ipam.status.${s}`);

async function loadIpam() {
  document.getElementById('ipam-conflicts')?.classList.add('hidden');
  const prefixes = await api('/ipam/prefixes');
  const dcs = await api('/datacenters');
  const dcMap = Object.fromEntries(dcs.map(d => [d.id, d.name]));
  const list = document.getElementById('ipam-prefix-list');
  if (!prefixes.length) {
    list.innerHTML = `<p class="muted">${t('ipam.no_prefixes')}</p>`;
    document.getElementById('ipam-address-panel')?.classList.add('hidden');
    return;
  }
  list.innerHTML = `<table class="data-table"><thead><tr>
    <th>${t('ipam.cidr')}</th><th>${t('ipam.datacenter')}</th><th>${t('ipam.vlan')}</th><th>${t('common.action')}</th>
  </tr></thead><tbody>${prefixes.map(p => `
    <tr>
      <td><strong>${p.cidr}</strong>${p.description ? `<br><span class="muted">${p.description}</span>` : ''}</td>
      <td>${dcMap[p.datacenter_id] || p.datacenter_id}</td>
      <td>${p.vlan || '—'}</td>
      <td><button class="btn-secondary" onclick="openIpamPrefix(${p.id}, '${p.cidr}')">${t('common.view')}</button></td>
    </tr>`).join('')}</tbody></table>`;

  const dcSel = document.getElementById('prefix-dc');
  if (dcSel && !dcSel.options.length) {
    dcSel.innerHTML = dcs.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
  }
}

async function openIpamPrefix(prefixId, cidr) {
  selectedPrefixId = prefixId;
  const panel = document.getElementById('ipam-address-panel');
  panel?.classList.remove('hidden');
  document.getElementById('ipam-address-title').textContent = cidr;
  const util = await api(`/ipam/prefixes/${prefixId}/utilization`);
  document.getElementById('ipam-utilization').innerHTML = `
    <div class="stat-card"><div class="value">${util.utilization_pct}%</div><div class="label">${t('ipam.utilization', { pct: util.utilization_pct, assigned: util.assigned, total: util.total })}</div></div>
    <div class="stat-card"><div class="value">${util.free}</div><div class="label">${t('ipam.status.free')}</div></div>
    <div class="stat-card"><div class="value">${util.reserved}</div><div class="label">${t('ipam.status.reserved')}</div></div>`;
  const addresses = await api(`/ipam/prefixes/${prefixId}/addresses`);
  document.querySelector('#ipam-address-table tbody').innerHTML = addresses.map(a => `
    <tr>
      <td>${a.address}</td>
      <td>${ipamStatusLabel(a.status)}</td>
      <td>${a.hostname || '—'}</td>
      <td>${a.asset_type ? `${a.asset_type} #${a.asset_id || ''}` : '—'}</td>
      <td>${hasPerm('manage_ipam') ? `<select onchange="updateIpAddress(${a.id}, this.value)">
        <option value="free" ${a.status === 'free' ? 'selected' : ''}>${t('ipam.status.free')}</option>
        <option value="reserved" ${a.status === 'reserved' ? 'selected' : ''}>${t('ipam.status.reserved')}</option>
        <option value="assigned" ${a.status === 'assigned' ? 'selected' : ''}>${t('ipam.status.assigned')}</option>
        <option value="dhcp" ${a.status === 'dhcp' ? 'selected' : ''}>${t('ipam.status.dhcp')}</option>
      </select>` : '—'}</td>
    </tr>`).join('');
}

async function updateIpAddress(id, status) {
  await api(`/ipam/addresses/${id}`, { method: 'PATCH', body: { status } });
  if (selectedPrefixId) {
    const title = document.getElementById('ipam-address-title')?.textContent;
    await openIpamPrefix(selectedPrefixId, title);
  }
}

document.getElementById('show-add-prefix')?.addEventListener('click', () => {
  document.getElementById('add-prefix-form')?.classList.remove('hidden');
});
document.getElementById('cancel-add-prefix')?.addEventListener('click', () => {
  document.getElementById('add-prefix-form')?.classList.add('hidden');
});
document.getElementById('prefix-create-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  await api('/ipam/prefixes', {
    method: 'POST',
    body: {
      datacenter_id: Number(document.getElementById('prefix-dc').value),
      cidr: document.getElementById('prefix-cidr').value,
      vlan: document.getElementById('prefix-vlan').value ? Number(document.getElementById('prefix-vlan').value) : null,
      gateway: document.getElementById('prefix-gateway').value || null,
      description: document.getElementById('prefix-desc').value || null,
    },
  });
  document.getElementById('add-prefix-form')?.classList.add('hidden');
  await loadIpam();
});
document.getElementById('refresh-ipam')?.addEventListener('click', loadIpam);
document.getElementById('ipam-sync-prefix')?.addEventListener('click', async () => {
  if (!selectedPrefixId) return;
  await api(`/ipam/prefixes/${selectedPrefixId}/sync`, { method: 'POST' });
  const title = document.getElementById('ipam-address-title')?.textContent;
  await openIpamPrefix(selectedPrefixId, title);
});
document.getElementById('ipam-sync-conflicts')?.addEventListener('click', async () => {
  const conflicts = await api('/ipam/conflicts');
  const box = document.getElementById('ipam-conflicts');
  if (!conflicts.length) {
    box.textContent = t('ipam.no_conflicts');
    box.classList.remove('hidden');
    box.classList.remove('error-box');
    box.classList.add('info-box');
    return;
  }
  box.innerHTML = `<strong>${t('ipam.conflicts_found', { count: conflicts.length })}</strong><ul>${conflicts.map(c =>
    `<li>${c.ip_address}: ${c.assets.map(a => `${a.name} (${a.type})`).join(', ')}</li>`).join('')}</ul>`;
  box.classList.remove('hidden');
  box.classList.add('error-box');
});

// --- Config Backups ---
let deviceNameMap = {};

async function loadBackups() {
  const [eligible, backups, devices] = await Promise.all([
    api('/backups/devices/eligible'),
    api('/backups'),
    api('/devices'),
  ]);
  deviceNameMap = Object.fromEntries(devices.map(d => [d.id, d.name]));
  const eligBody = document.querySelector('#eligible-devices-table tbody');
  eligBody.innerHTML = eligible.length ? eligible.map(d => `
    <tr>
      <td>${d.name}</td><td>${vendorLabel(d.vendor)}</td><td>${d.ip_address}</td>
      <td>${d.has_ssh ? '✓' : '—'}</td>
      <td>${hasPerm('manage_devices') && d.has_ssh ? `<button onclick="backupDeviceNow(${d.id})">${t('backups.backup_now')}</button>` : '—'}</td>
    </tr>`).join('') : `<tr><td colspan="5" class="muted">${t('backups.no_eligible')}</td></tr>`;

  document.querySelector('#backups-table tbody').innerHTML = backups.length ? backups.map(b => `
    <tr>
      <td>${b.id}</td><td>${deviceNameMap[b.device_id] || b.device_id}</td>
      <td><code>${b.content_hash.slice(0, 12)}…</code></td>
      <td>${(b.size_bytes / 1024).toFixed(1)} KB</td>
      <td>${localeDate(b.collected_at)}</td>
      <td><button class="btn-secondary" onclick="viewBackup(${b.id})">${t('backups.view')}</button></td>
    </tr>`).join('') : `<tr><td colspan="6" class="muted">—</td></tr>`;
}

async function backupDeviceNow(deviceId) {
  try {
    await api(`/backups/devices/${deviceId}`, { method: 'POST' });
    await loadBackups();
  } catch (err) {
    alert(err.message);
  }
}

async function viewBackup(id) {
  const data = await api(`/backups/${id}`);
  const el = document.getElementById('backup-content-view');
  el.textContent = data.content;
  el.classList.remove('hidden');
}

document.getElementById('run-all-backups')?.addEventListener('click', async () => {
  const result = await api('/backups/run-all', { method: 'POST' });
  alert(t('backups.run_result', result));
  await loadBackups();
});
document.getElementById('refresh-backups')?.addEventListener('click', loadBackups);

// --- Integrations ---
let integrationsCache = [];

function updateIntegrationFormFields() {
  const type = document.getElementById('int-type')?.value || 'prtg';
  const userLabel = document.getElementById('int-user-label');
  const tokenLabel = document.getElementById('int-token-label');
  const tokenInput = document.getElementById('int-token');
  if (!userLabel || !tokenLabel) return;
  if (type === 'prtg') {
    userLabel.classList.add('hidden');
    tokenLabel.classList.remove('hidden');
    if (tokenInput) tokenInput.placeholder = t('integrations.token_placeholder_prtg');
  } else {
    userLabel.classList.remove('hidden');
    tokenLabel.classList.remove('hidden');
    if (tokenInput) tokenInput.placeholder = t('integrations.token_placeholder_vmware');
  }
}

function renderIntegrationDetail(item) {
  const panel = document.getElementById('integration-detail');
  if (!panel || !item) return;
  panel.classList.remove('hidden');
  const summary = item.extra?.prtg_summary;
  const vmware = item.extra?.vmware_metrics;
  let statsHtml = '';
  if (item.integration_type === 'prtg' && summary) {
    statsHtml = `<div class="stats-grid integration-stats">
      <div class="stat-card"><div class="value">${summary.total || 0}</div><div class="label">${t('integrations.sensors_total')}</div></div>
      <div class="stat-card"><div class="value status-online">${summary.up || 0}</div><div class="label">${t('integrations.sensors_up')}</div></div>
      <div class="stat-card"><div class="value">${summary.warning || 0}</div><div class="label">${t('integrations.sensors_warning')}</div></div>
      <div class="stat-card"><div class="value">${summary.down || 0}</div><div class="label">${t('integrations.sensors_down')}</div></div>
    </div>`;
  } else if (item.integration_type === 'vmware' && vmware) {
    statsHtml = `<div class="stats-grid integration-stats">${Object.entries(vmware).map(([k, v]) =>
      `<div class="stat-card"><div class="value">${v}</div><div class="label">${k}</div></div>`).join('')}</div>`;
  } else {
    statsHtml = `<p class="muted">${t('integrations.no_sync_data')}</p>`;
  }
  panel.innerHTML = `
    <div class="toolbar">
      <h3>${item.name} — ${item.integration_type.toUpperCase()}</h3>
      <div class="toolbar-actions">
        <a href="${item.base_url}" target="_blank" rel="noopener" class="btn-secondary">${t('integrations.open_external')}</a>
        ${canManageIntegrations() ? `
          <button class="btn-secondary" onclick="testIntegration(${item.id})">${t('integrations.test')}</button>
          <button onclick="syncIntegration(${item.id})">${t('integrations.sync')}</button>` : ''}
      </div>
    </div>
    <p class="muted">${t('integrations.url')}: <a href="${item.base_url}" target="_blank" rel="noopener">${item.base_url}</a></p>
    <p class="muted">${t('integrations.last_sync')}: ${item.last_sync_at ? localeDate(item.last_sync_at) : '—'} — ${item.last_sync_status || '—'}</p>
    ${statsHtml}
  `;
}

async function loadIntegrations() {
  const items = await api('/integrations');
  integrationsCache = items;
  const dcs = await api('/datacenters');
  const intDc = document.getElementById('int-dc');
  if (intDc && intDc.options.length <= 1) {
    intDc.innerHTML = `<option value="">—</option>` + dcs.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
  }
  document.getElementById('integrations-empty-cta')?.classList.toggle('hidden', items.length > 0 || !canManageIntegrations());
  document.querySelector('#integrations-table tbody').innerHTML = items.length ? items.map(i => `
    <tr class="integration-row" onclick="viewIntegration(${i.id})">
      <td><strong>${i.name}</strong></td>
      <td>${i.integration_type.toUpperCase()}</td>
      <td><a href="${i.base_url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${i.base_url}</a></td>
      <td>${i.last_sync_at ? localeDate(i.last_sync_at) : '—'}</td>
      <td>${i.last_sync_status || (i.enabled ? '—' : 'disabled')}</td>
      <td onclick="event.stopPropagation()">${canManageIntegrations() ? `
        <button class="btn-secondary" onclick="testIntegration(${i.id})">${t('integrations.test')}</button>
        <button onclick="syncIntegration(${i.id})">${t('integrations.sync')}</button>` : `<button class="btn-secondary" onclick="viewIntegration(${i.id})">${t('common.view')}</button>`}</td>
    </tr>`).join('') : `<tr><td colspan="6" class="muted">${t('integrations.no_items')}</td></tr>`;
  if (items.length === 1) renderIntegrationDetail(items[0]);
  else document.getElementById('integration-detail')?.classList.add('hidden');
  updateIntegrationFormFields();
}

function viewIntegration(id) {
  const item = integrationsCache.find(i => i.id === id);
  if (item) renderIntegrationDetail(item);
}

async function testIntegration(id) {
  try {
    const r = await api(`/integrations/${id}/test`, { method: 'POST' });
    alert(r.ok ? `${t('integrations.test_ok')}: ${r.message}` : `${t('integrations.test_fail')}: ${r.message}`);
  } catch (err) {
    alert(err.message);
  }
}

async function syncIntegration(id) {
  try {
    const result = await api(`/integrations/${id}/sync`, { method: 'POST' });
    alert(t('integrations.sync_ok'));
    await loadIntegrations();
    viewIntegration(id);
    if (result?.summary) renderIntegrationDetail({ ...integrationsCache.find(i => i.id === id), extra: { prtg_summary: result.summary } });
  } catch (err) {
    alert(err.message);
  }
}

function openAddIntegrationForm() {
  document.getElementById('add-integration-form')?.classList.remove('hidden');
  updateIntegrationFormFields();
}

document.getElementById('show-add-integration')?.addEventListener('click', openAddIntegrationForm);
document.getElementById('integrations-empty-add')?.addEventListener('click', openAddIntegrationForm);
document.getElementById('int-type')?.addEventListener('change', updateIntegrationFormFields);
document.getElementById('cancel-add-integration')?.addEventListener('click', () => {
  document.getElementById('add-integration-form')?.classList.add('hidden');
});
document.getElementById('integration-create-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const dcVal = document.getElementById('int-dc').value;
  await api('/integrations', {
    method: 'POST',
    body: {
      name: document.getElementById('int-name').value,
      integration_type: document.getElementById('int-type').value,
      base_url: document.getElementById('int-url').value,
      datacenter_id: dcVal ? Number(dcVal) : null,
      username: document.getElementById('int-username').value || null,
      api_token: document.getElementById('int-token').value || null,
    },
  });
  document.getElementById('add-integration-form')?.classList.add('hidden');
  await loadIntegrations();
});
document.getElementById('sync-all-integrations')?.addEventListener('click', async () => {
  await api('/integrations/sync-all', { method: 'POST' });
  alert(t('integrations.sync_ok'));
  await loadIntegrations();
});
document.getElementById('refresh-integrations')?.addEventListener('click', loadIntegrations);

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

window.openSwitchDetail = openSwitchDetail;
window.closeSwitchDetail = closeSwitchDetail;
window.showPortDetail = showPortDetail;
window.openDatacenterDetail = openDatacenterDetail;
window.switchDcTab = switchDcTab;
window.ackAlert = ackAlert;
window.resolveAlert = resolveAlert;
window.downloadDcReport = downloadDcReport;
window.viewIntegration = viewIntegration;
window.openIpamPrefix = openIpamPrefix;
window.updateIpAddress = updateIpAddress;
window.backupDeviceNow = backupDeviceNow;
window.viewBackup = viewBackup;
window.testIntegration = testIntegration;
window.syncIntegration = syncIntegration;

if (token) {
  initApp().catch(() => logout());
} else {
  showPanel('login');
}
