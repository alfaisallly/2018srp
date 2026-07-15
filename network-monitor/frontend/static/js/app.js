const state = {
  overview: null,
  alerts: [],
  selectedId: null,
  detail: null,
  filterQ: "",
  filterStatus: "all",
};

const els = {
  fleetHeadline: document.getElementById("fleet-headline"),
  fleetSub: document.getElementById("fleet-sub"),
  targetRows: document.getElementById("target-rows"),
  alertList: document.getElementById("alert-list"),
  detailEmpty: document.getElementById("detail-empty"),
  detailBody: document.getElementById("detail-body"),
  detailName: document.getElementById("detail-name"),
  detailHost: document.getElementById("detail-host"),
  detailStatus: document.getElementById("detail-status"),
  detailMsg: document.getElementById("detail-msg"),
  historyList: document.getElementById("history-list"),
  sparkline: document.getElementById("sparkline"),
  modal: document.getElementById("modal-add"),
  formAdd: document.getElementById("form-add"),
  filterQ: document.getElementById("filter-q"),
  filterStatus: document.getElementById("filter-status"),
  btnToggle: document.getElementById("btn-toggle"),
};

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

function fmtLatency(ms) {
  if (ms == null || Number.isNaN(ms)) return "—";
  return `${Number(ms).toFixed(1)} ms`;
}

function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function relativeAge(iso) {
  if (!iso) return "never";
  const sec = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (sec < 60) return `${Math.floor(sec)}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
}

function setStats(counts, openAlerts) {
  for (const key of ["up", "down", "degraded", "unknown"]) {
    const node = document.querySelector(`[data-stat="${key}"]`);
    if (node) node.textContent = String(counts[key] || 0);
  }
  const alerts = document.querySelector(`[data-stat="alerts"]`);
  if (alerts) alerts.textContent = String(openAlerts || 0);

  const up = counts.up || 0;
  const down = counts.down || 0;
  const degraded = counts.degraded || 0;
  if (down > 0) {
    els.fleetHeadline.textContent = `${down} endpoint${down === 1 ? "" : "s"} down`;
  } else if (degraded > 0) {
    els.fleetHeadline.textContent = `Fleet mostly healthy · ${degraded} degraded`;
  } else if (up > 0) {
    els.fleetHeadline.textContent = `All monitored paths look healthy`;
  } else {
    els.fleetHeadline.textContent = `Waiting for first probe results`;
  }
}

function filteredTargets() {
  const targets = state.overview?.targets || [];
  const q = state.filterQ.trim().toLowerCase();
  return targets.filter((t) => {
    if (state.filterStatus !== "all" && t.status !== state.filterStatus) return false;
    if (!q) return true;
    const hay = `${t.name} ${t.host} ${(t.tags || []).join(" ")} ${t.check_type}`.toLowerCase();
    return hay.includes(q);
  });
}

function renderTargets() {
  const rows = filteredTargets();
  els.targetRows.innerHTML = rows
    .map((t) => {
      const latest = t.latest || {};
      const tags = (t.tags || [])
        .slice(0, 3)
        .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
        .join("");
      const probe =
        t.check_type === "ping"
          ? "ping"
          : t.check_type === "tcp"
            ? `tcp:${t.port || "?"}`
            : `http${t.port ? ":" + t.port : ""}`;
      return `
        <tr data-id="${t.id}" class="${state.selectedId === t.id ? "active" : ""}">
          <td><span class="status-dot ${t.status}">${escapeHtml(t.status || "unknown")}</span></td>
          <td>${escapeHtml(t.name)}${tags}</td>
          <td class="mono">${escapeHtml(t.host)}</td>
          <td class="mono">${escapeHtml(probe)}</td>
          <td class="mono">${fmtLatency(latest.latency_ms)}</td>
          <td>${relativeAge(latest.checked_at)}</td>
          <td><button type="button" class="btn ghost row-check" data-check="${t.id}">Check</button></td>
        </tr>`;
    })
    .join("");

  if (!rows.length) {
    els.targetRows.innerHTML = `<tr><td colspan="7" style="color:var(--ink-soft);padding:1.2rem">No targets match this filter.</td></tr>`;
  }
}

function renderAlerts() {
  if (!state.alerts.length) {
    els.alertList.innerHTML = `<li class="alert-meta">No alerts yet. Status transitions will appear here.</li>`;
    return;
  }
  els.alertList.innerHTML = state.alerts
    .map((a) => {
      return `
        <li>
          <div class="alert-title">${escapeHtml(a.title)}</div>
          <div class="alert-meta">${escapeHtml(a.target_name)} · ${escapeHtml(a.severity)} · ${fmtTime(a.created_at)}</div>
          <div class="alert-meta">${escapeHtml(a.detail || "")}</div>
          ${
            a.acknowledged
              ? ""
              : `<button type="button" class="btn ghost" data-ack="${a.id}">Acknowledge</button>`
          }
        </li>`;
    })
    .join("");
}

function renderDetail() {
  if (!state.detail) {
    els.detailEmpty.classList.remove("hidden");
    els.detailBody.classList.add("hidden");
    return;
  }
  const d = state.detail;
  const latest = d.latest || {};
  els.detailEmpty.classList.add("hidden");
  els.detailBody.classList.remove("hidden");
  els.detailName.textContent = d.name;
  els.detailHost.textContent = d.host;
  els.detailStatus.textContent = d.status || "unknown";
  els.detailStatus.className = `pill ${d.status || "unknown"}`;
  els.detailMsg.textContent = latest.message || "No probe message yet.";
  els.btnToggle.textContent = d.enabled ? "Disable" : "Enable";

  const history = d.history || [];
  els.historyList.innerHTML = history
    .slice()
    .reverse()
    .slice(0, 12)
    .map(
      (h) =>
        `<li><span class="status-dot ${h.status}">${h.status}</span> · ${fmtLatency(h.latency_ms)} · ${fmtTime(h.checked_at)} · ${escapeHtml(h.message || "")}</li>`
    )
    .join("");

  drawSparkline(history.map((h) => h.latency_ms).filter((v) => v != null));
}

function drawSparkline(values) {
  const svg = els.sparkline;
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  if (values.length < 2) {
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", "12");
    text.setAttribute("y", "44");
    text.setAttribute("fill", "#4a5d73");
    text.setAttribute("font-size", "12");
    text.textContent = "Not enough latency samples yet";
    svg.appendChild(text);
    return;
  }
  const w = 320;
  const h = 80;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * (w - 8) + 4;
    const y = h - 8 - ((v - min) / span) * (h - 16);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", `M ${pts.join(" L ")}`);
  svg.appendChild(path);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function refreshOverview() {
  const [overview, alerts] = await Promise.all([
    api("/api/overview"),
    api("/api/alerts?limit=40"),
  ]);
  state.overview = overview;
  state.alerts = alerts;
  setStats(overview.counts, overview.open_alerts);
  const total = Object.values(overview.counts).reduce((a, b) => a + b, 0);
  els.fleetSub.textContent = `${total} targets monitored · updated ${fmtTime(overview.generated_at)}`;
  renderTargets();
  renderAlerts();
  if (state.selectedId) {
    await loadDetail(state.selectedId, false);
  }
}

async function loadDetail(id, select = true) {
  if (select) state.selectedId = id;
  state.detail = await api(`/api/targets/${id}`);
  renderDetail();
  renderTargets();
}

document.getElementById("btn-refresh").addEventListener("click", async () => {
  await api("/api/checks/run", { method: "POST" });
  await refreshOverview();
});

document.getElementById("btn-discover").addEventListener("click", async () => {
  const result = await api("/api/discover/import", {
    method: "POST",
    body: JSON.stringify({ import_as_ping: true }),
  });
  alert(`Imported ${result.imported} discovered host(s).`);
  await refreshOverview();
});

document.getElementById("btn-add").addEventListener("click", () => {
  els.modal.showModal();
});

document.getElementById("btn-cancel-add").addEventListener("click", () => {
  els.modal.close();
});

els.formAdd.addEventListener("submit", async (event) => {
  event.preventDefault();
  const fd = new FormData(els.formAdd);
  const payload = {
    name: String(fd.get("name") || "").trim(),
    host: String(fd.get("host") || "").trim(),
    check_type: String(fd.get("check_type") || "ping"),
    path: String(fd.get("path") || "/") || "/",
    tags: String(fd.get("tags") || "")
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean),
    notes: String(fd.get("notes") || ""),
  };
  const portRaw = String(fd.get("port") || "").trim();
  if (portRaw) payload.port = Number(portRaw);
  if (payload.check_type === "tcp" && !payload.port) {
    alert("TCP checks need a port.");
    return;
  }
  await api("/api/targets", { method: "POST", body: JSON.stringify(payload) });
  els.formAdd.reset();
  els.modal.close();
  await refreshOverview();
});

els.targetRows.addEventListener("click", async (event) => {
  const checkBtn = event.target.closest("[data-check]");
  if (checkBtn) {
    event.stopPropagation();
    const id = Number(checkBtn.dataset.check);
    await api(`/api/targets/${id}/check`, { method: "POST" });
    await refreshOverview();
    await loadDetail(id);
    return;
  }
  const row = event.target.closest("tr[data-id]");
  if (!row) return;
  await loadDetail(Number(row.dataset.id));
});

els.alertList.addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-ack]");
  if (!btn) return;
  await api(`/api/alerts/${btn.dataset.ack}/ack`, { method: "POST" });
  await refreshOverview();
});

document.getElementById("btn-check-one").addEventListener("click", async () => {
  if (!state.selectedId) return;
  await api(`/api/targets/${state.selectedId}/check`, { method: "POST" });
  await refreshOverview();
  await loadDetail(state.selectedId);
});

document.getElementById("btn-delete").addEventListener("click", async () => {
  if (!state.selectedId) return;
  if (!confirm("Remove this target from monitoring?")) return;
  await api(`/api/targets/${state.selectedId}`, { method: "DELETE" });
  state.selectedId = null;
  state.detail = null;
  renderDetail();
  await refreshOverview();
});

els.btnToggle.addEventListener("click", async () => {
  if (!state.detail) return;
  await api(`/api/targets/${state.detail.id}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled: !state.detail.enabled }),
  });
  await refreshOverview();
  await loadDetail(state.detail.id);
});

els.filterQ.addEventListener("input", (e) => {
  state.filterQ = e.target.value;
  renderTargets();
});

els.filterStatus.addEventListener("change", (e) => {
  state.filterStatus = e.target.value;
  renderTargets();
});

async function boot() {
  try {
    await refreshOverview();
  } catch (err) {
    els.fleetHeadline.textContent = "Unable to reach NetPulse API";
    els.fleetSub.textContent = String(err.message || err);
  }
  setInterval(() => {
    refreshOverview().catch(() => {});
  }, 8000);
}

boot();
