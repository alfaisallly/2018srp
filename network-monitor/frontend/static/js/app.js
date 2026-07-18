/* NetPulse dashboard — Safari-compatible classic script (no modules). */
(function () {
  "use strict";

  var state = {
    overview: null,
    alerts: [],
    selectedId: null,
    detail: null,
    filterQ: "",
    filterStatus: "all",
  };

  var els = {
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

  function eventEl(event) {
    var t = event.target;
    if (!t) return null;
    return t.nodeType === 1 ? t : t.parentElement;
  }

  function closest(el, selector) {
    if (!el) return null;
    if (el.closest) return el.closest(selector);
    while (el && el.nodeType === 1) {
      if (el.matches && el.matches(selector)) return el;
      if (el.msMatchesSelector && el.msMatchesSelector(selector)) return el;
      if (el.webkitMatchesSelector && el.webkitMatchesSelector(selector)) return el;
      el = el.parentElement;
    }
    return null;
  }

  function openModal() {
    els.modal.hidden = false;
    document.body.style.overflow = "hidden";
    var first = els.formAdd.querySelector("input, select, textarea, button");
    if (first && first.focus) first.focus();
  }

  function closeModal() {
    els.modal.hidden = true;
    document.body.style.overflow = "";
  }

  function api(path, options) {
    options = options || {};
    var method = (options.method || "GET").toUpperCase();
    var headers = {};
    if (options.headers) {
      Object.keys(options.headers).forEach(function (k) {
        headers[k] = options.headers[k];
      });
    }
    // Safari can mishandle Content-Type on GET/HEAD with no body.
    if (method !== "GET" && method !== "HEAD" && options.body != null) {
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
    var init = {
      method: method,
      headers: headers,
      credentials: "same-origin",
      cache: "no-store",
    };
    if (options.body != null) init.body = options.body;

    return fetch(path, init).then(function (res) {
      if (!res.ok) {
        return res
          .json()
          .catch(function () {
            return {};
          })
          .then(function (body) {
            var detail = body.detail || res.statusText || "Request failed";
            throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
          });
      }
      if (res.status === 204) return null;
      return res.json();
    });
  }

  function fmtLatency(ms) {
    if (ms == null || Number.isNaN(Number(ms))) return "-";
    return Number(ms).toFixed(1) + " ms";
  }

  function fmtTime(iso) {
    if (!iso) return "-";
    var d = new Date(iso);
    try {
      return d.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch (e) {
      return d.toLocaleTimeString();
    }
  }

  function relativeAge(iso) {
    if (!iso) return "never";
    var sec = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (sec < 60) return Math.floor(sec) + "s ago";
    if (sec < 3600) return Math.floor(sec / 60) + "m ago";
    return Math.floor(sec / 3600) + "h ago";
  }

  function setStats(counts, openAlerts) {
    ["up", "down", "degraded", "unknown"].forEach(function (key) {
      var node = document.querySelector('[data-stat="' + key + '"]');
      if (node) node.textContent = String(counts[key] || 0);
    });
    var alerts = document.querySelector('[data-stat="alerts"]');
    if (alerts) alerts.textContent = String(openAlerts || 0);

    var up = counts.up || 0;
    var down = counts.down || 0;
    var degraded = counts.degraded || 0;
    if (down > 0) {
      els.fleetHeadline.textContent =
        down + " endpoint" + (down === 1 ? "" : "s") + " down";
    } else if (degraded > 0) {
      els.fleetHeadline.textContent =
        "Fleet mostly healthy · " + degraded + " degraded";
    } else if (up > 0) {
      els.fleetHeadline.textContent = "All monitored paths look healthy";
    } else {
      els.fleetHeadline.textContent = "Waiting for first probe results";
    }
  }

  function filteredTargets() {
    var targets = (state.overview && state.overview.targets) || [];
    var q = state.filterQ.trim().toLowerCase();
    return targets.filter(function (t) {
      if (state.filterStatus !== "all" && t.status !== state.filterStatus) return false;
      if (!q) return true;
      var hay = (
        t.name +
        " " +
        t.host +
        " " +
        (t.tags || []).join(" ") +
        " " +
        t.check_type
      ).toLowerCase();
      return hay.indexOf(q) !== -1;
    });
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderTargets() {
    var rows = filteredTargets();
    if (!rows.length) {
      els.targetRows.innerHTML =
        '<tr><td colspan="7" style="color:var(--ink-soft);padding:1.2rem">No targets match this filter.</td></tr>';
      return;
    }
    els.targetRows.innerHTML = rows
      .map(function (t) {
        var latest = t.latest || {};
        var tags = (t.tags || [])
          .slice(0, 3)
          .map(function (tag) {
            return '<span class="tag">' + escapeHtml(tag) + "</span>";
          })
          .join("");
        var probe =
          t.check_type === "ping"
            ? "ping"
            : t.check_type === "tcp"
              ? "tcp:" + (t.port || "?")
              : "http" + (t.port ? ":" + t.port : "");
        return (
          '<tr data-id="' +
          t.id +
          '" class="' +
          (state.selectedId === t.id ? "active" : "") +
          '">' +
          '<td><span class="status-dot ' +
          escapeHtml(t.status || "unknown") +
          '">' +
          escapeHtml(t.status || "unknown") +
          "</span></td>" +
          "<td>" +
          escapeHtml(t.name) +
          tags +
          "</td>" +
          '<td class="mono">' +
          escapeHtml(t.host) +
          "</td>" +
          '<td class="mono">' +
          escapeHtml(probe) +
          "</td>" +
          '<td class="mono">' +
          fmtLatency(latest.latency_ms) +
          "</td>" +
          "<td>" +
          relativeAge(latest.checked_at) +
          "</td>" +
          '<td><button type="button" class="btn ghost row-check" data-check="' +
          t.id +
          '">Check</button></td>' +
          "</tr>"
        );
      })
      .join("");
  }

  function renderAlerts() {
    if (!state.alerts.length) {
      els.alertList.innerHTML =
        '<li class="alert-meta">No alerts yet. Status transitions will appear here.</li>';
      return;
    }
    els.alertList.innerHTML = state.alerts
      .map(function (a) {
        return (
          "<li>" +
          '<div class="alert-title">' +
          escapeHtml(a.title) +
          "</div>" +
          '<div class="alert-meta">' +
          escapeHtml(a.target_name) +
          " · " +
          escapeHtml(a.severity) +
          " · " +
          fmtTime(a.created_at) +
          "</div>" +
          '<div class="alert-meta">' +
          escapeHtml(a.detail || "") +
          "</div>" +
          (a.acknowledged
            ? ""
            : '<button type="button" class="btn ghost" data-ack="' +
              a.id +
              '">Acknowledge</button>') +
          "</li>"
        );
      })
      .join("");
  }

  function drawSparkline(values) {
    var svg = els.sparkline;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    if (values.length < 2) {
      var text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", "12");
      text.setAttribute("y", "44");
      text.setAttribute("fill", "#4a5d73");
      text.setAttribute("font-size", "12");
      text.textContent = "Not enough latency samples yet";
      svg.appendChild(text);
      return;
    }
    var w = 320;
    var h = 80;
    var min = Math.min.apply(null, values);
    var max = Math.max.apply(null, values);
    var span = Math.max(max - min, 1);
    var pts = values.map(function (v, i) {
      var x = (i / (values.length - 1)) * (w - 8) + 4;
      var y = h - 8 - ((v - min) / span) * (h - 16);
      return x.toFixed(1) + "," + y.toFixed(1);
    });
    var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M " + pts.join(" L "));
    svg.appendChild(path);
  }

  function renderDetail() {
    if (!state.detail) {
      els.detailEmpty.classList.remove("hidden");
      els.detailBody.classList.add("hidden");
      return;
    }
    var d = state.detail;
    var latest = d.latest || {};
    els.detailEmpty.classList.add("hidden");
    els.detailBody.classList.remove("hidden");
    els.detailName.textContent = d.name;
    els.detailHost.textContent = d.host;
    els.detailStatus.textContent = d.status || "unknown";
    els.detailStatus.className = "pill " + (d.status || "unknown");
    els.detailMsg.textContent = latest.message || "No probe message yet.";
    els.btnToggle.textContent = d.enabled ? "Disable" : "Enable";

    var history = d.history || [];
    els.historyList.innerHTML = history
      .slice()
      .reverse()
      .slice(0, 12)
      .map(function (h) {
        return (
          "<li><span class=\"status-dot " +
          h.status +
          '">' +
          h.status +
          "</span> · " +
          fmtLatency(h.latency_ms) +
          " · " +
          fmtTime(h.checked_at) +
          " · " +
          escapeHtml(h.message || "") +
          "</li>"
        );
      })
      .join("");

    drawSparkline(
      history
        .map(function (h) {
          return h.latency_ms;
        })
        .filter(function (v) {
          return v != null;
        })
    );
  }

  function refreshOverview() {
    return Promise.all([
      api("/api/overview"),
      api("/api/alerts?limit=40"),
    ]).then(function (results) {
      state.overview = results[0];
      state.alerts = results[1];
      setStats(state.overview.counts, state.overview.open_alerts);
      var total = 0;
      Object.keys(state.overview.counts).forEach(function (k) {
        total += state.overview.counts[k] || 0;
      });
      els.fleetSub.textContent =
        total +
        " targets monitored · updated " +
        fmtTime(state.overview.generated_at);
      renderTargets();
      renderAlerts();
      if (state.selectedId) {
        return loadDetail(state.selectedId, false);
      }
    });
  }

  function loadDetail(id, select) {
    if (select !== false) state.selectedId = id;
    return api("/api/targets/" + id).then(function (detail) {
      state.detail = detail;
      renderDetail();
      renderTargets();
    });
  }

  document.getElementById("btn-refresh").addEventListener("click", function () {
    api("/api/checks/run", { method: "POST" })
      .then(function () {
        return refreshOverview();
      })
      .catch(function (err) {
        alert(String(err.message || err));
      });
  });

  document.getElementById("btn-discover").addEventListener("click", function () {
    api("/api/discover/import", {
      method: "POST",
      body: JSON.stringify({ import_as_ping: true }),
    })
      .then(function (result) {
        alert("Imported " + result.imported + " discovered host(s).");
        return refreshOverview();
      })
      .catch(function (err) {
        alert(String(err.message || err));
      });
  });

  document.getElementById("btn-add").addEventListener("click", openModal);
  document.getElementById("btn-cancel-add").addEventListener("click", closeModal);

  els.modal.addEventListener("click", function (event) {
    if (event.target === els.modal) closeModal();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !els.modal.hidden) closeModal();
  });

  els.formAdd.addEventListener("submit", function (event) {
    event.preventDefault();
    var fd = new FormData(els.formAdd);
    var payload = {
      name: String(fd.get("name") || "").trim(),
      host: String(fd.get("host") || "").trim(),
      check_type: String(fd.get("check_type") || "ping"),
      path: String(fd.get("path") || "/") || "/",
      tags: String(fd.get("tags") || "")
        .split(",")
        .map(function (t) {
          return t.trim();
        })
        .filter(Boolean),
      notes: String(fd.get("notes") || ""),
    };
    var portRaw = String(fd.get("port") || "").trim();
    if (portRaw) payload.port = Number(portRaw);
    if (payload.check_type === "tcp" && !payload.port) {
      alert("TCP checks need a port.");
      return;
    }
    api("/api/targets", {
      method: "POST",
      body: JSON.stringify(payload),
    })
      .then(function () {
        els.formAdd.reset();
        closeModal();
        return refreshOverview();
      })
      .catch(function (err) {
        alert(String(err.message || err));
      });
  });

  els.targetRows.addEventListener("click", function (event) {
    var root = eventEl(event);
    var checkBtn = closest(root, "[data-check]");
    if (checkBtn) {
      event.stopPropagation();
      var checkId = Number(checkBtn.getAttribute("data-check"));
      api("/api/targets/" + checkId + "/check", { method: "POST" })
        .then(function () {
          return refreshOverview();
        })
        .then(function () {
          return loadDetail(checkId);
        })
        .catch(function (err) {
          alert(String(err.message || err));
        });
      return;
    }
    var row = closest(root, "tr[data-id]");
    if (!row) return;
    loadDetail(Number(row.getAttribute("data-id"))).catch(function (err) {
      alert(String(err.message || err));
    });
  });

  els.alertList.addEventListener("click", function (event) {
    var btn = closest(eventEl(event), "[data-ack]");
    if (!btn) return;
    api("/api/alerts/" + btn.getAttribute("data-ack") + "/ack", {
      method: "POST",
    })
      .then(function () {
        return refreshOverview();
      })
      .catch(function (err) {
        alert(String(err.message || err));
      });
  });

  document.getElementById("btn-check-one").addEventListener("click", function () {
    if (!state.selectedId) return;
    api("/api/targets/" + state.selectedId + "/check", { method: "POST" })
      .then(function () {
        return refreshOverview();
      })
      .then(function () {
        return loadDetail(state.selectedId);
      })
      .catch(function (err) {
        alert(String(err.message || err));
      });
  });

  document.getElementById("btn-delete").addEventListener("click", function () {
    if (!state.selectedId) return;
    if (!confirm("Remove this target from monitoring?")) return;
    api("/api/targets/" + state.selectedId, { method: "DELETE" })
      .then(function () {
        state.selectedId = null;
        state.detail = null;
        renderDetail();
        return refreshOverview();
      })
      .catch(function (err) {
        alert(String(err.message || err));
      });
  });

  els.btnToggle.addEventListener("click", function () {
    if (!state.detail) return;
    api("/api/targets/" + state.detail.id, {
      method: "PATCH",
      body: JSON.stringify({ enabled: !state.detail.enabled }),
    })
      .then(function () {
        return refreshOverview();
      })
      .then(function () {
        return loadDetail(state.detail.id);
      })
      .catch(function (err) {
        alert(String(err.message || err));
      });
  });

  els.filterQ.addEventListener("input", function (e) {
    state.filterQ = e.target.value;
    renderTargets();
  });

  els.filterStatus.addEventListener("change", function (e) {
    state.filterStatus = e.target.value;
    renderTargets();
  });

  function boot() {
    refreshOverview().catch(function (err) {
      els.fleetHeadline.textContent = "Unable to reach NetPulse API";
      els.fleetSub.textContent = String(err.message || err);
    });
    setInterval(function () {
      refreshOverview().catch(function () {});
    }, 8000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
