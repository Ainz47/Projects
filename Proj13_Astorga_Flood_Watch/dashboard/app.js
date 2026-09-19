// Astorga Central -- Flood Watch operations dashboard.
// Talks to the FastAPI backend. Derived from the page's own host so this works
// unmodified whether it's loaded as localhost (laptop) or a LAN/hotspot IP (phone).
const API_BASE = `http://${window.location.hostname}:8000`;
const REFRESH_MS = 1000; // 1 Hz so the live ESP node's readings show in near-real-time
const ASTORGA_CENTER = [6.9116, 125.4611];

const STATUS_COLOR = {
  normal: "#2fb380",
  watch: "#f4b740",
  critical: "#e4483b",
};
const STATUS_RANK = { normal: 0, watch: 1, critical: 2 };

let map, chart;
let markers = {}; // pin id -> leaflet layer
let selectedId = null;
let chokePointCache = {}; // id -> choke point (for thresholds in the chart)

// ---- Map setup -------------------------------------------------------------
function initMap() {
  map = L.map("map", { zoomControl: true }).setView(ASTORGA_CENTER, 15);
  // OpenStreetMap tiles. CartoDB's basemap.cartocdn.com is DNS-blocked on some
  // networks (campus/enterprise); OSM's tile host resolves where CARTO doesn't.
  L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      attribution:
        '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }
  ).addTo(map);

  const legend = L.control({ position: "bottomright" });
  legend.onAdd = () => {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML =
      '<div class="row"><span class="dot" style="background:#2fb380"></span>Normal</div>' +
      '<div class="row"><span class="dot" style="background:#f4b740"></span>Watch</div>' +
      '<div class="row"><span class="dot" style="background:#e4483b"></span>Critical</div>' +
      '<div class="row"><span class="dot" style="background:#7c93ff"></span>Citizen report</div>';
    return div;
  };
  legend.addTo(map);
}

// ---- Data fetch ------------------------------------------------------------
async function getJSON(path) {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

async function refresh() {
  let chokePoints, reports;
  try {
    [chokePoints, reports] = await Promise.all([
      getJSON("/api/flood/choke-points"),
      getJSON("/api/reports"),
    ]);
  } catch (err) {
    console.warn("Backend unreachable:", err.message);
    return; // keep last-known state on screen rather than blanking the board
  }

  // Latest water level per point (limit=1). Small N -- fine for a barangay.
  const latest = await Promise.all(
    chokePoints.map((cp) =>
      getJSON(`/api/flood/choke-points/${cp.id}/history?limit=1`)
        .then((rows) => (rows.length ? rows[rows.length - 1].water_level_cm : null))
        .catch(() => null)
    )
  );

  chokePointCache = {};
  chokePoints.forEach((cp) => (chokePointCache[cp.id] = cp));

  renderChokePoints(chokePoints, latest);
  renderReports(reports);
  renderMap(chokePoints, reports);
  updateOverall(chokePoints);

  if (selectedId !== null && chokePointCache[selectedId]) {
    loadHistory(selectedId);
  }
}

// ---- Choke-point cards -----------------------------------------------------
function renderChokePoints(chokePoints, latest) {
  const list = document.getElementById("cp-list");
  if (!chokePoints.length) {
    list.innerHTML = '<div class="empty">No choke points seeded. Run seed.py.</div>';
    return;
  }
  list.innerHTML = "";
  chokePoints.forEach((cp, i) => {
    const level = latest[i];
    const pct = level == null ? 0 : Math.min(100, Math.max(0, (level / cp.critical_threshold_cm) * 100));
    const card = document.createElement("div");
    card.className = `cp status-${cp.current_status}` + (cp.id === selectedId ? " selected" : "");
    card.innerHTML = `
      <div class="cp-head">
        <span class="cp-name">${escapeHtml(cp.name)}</span>
        <span class="cp-status">${cp.current_status}</span>
      </div>
      <div class="cp-sim">${cp.is_simulated ? "◇ simulated node" : "● live ESP32 node"}</div>
      <div class="gauge">
        <div class="track"><div class="fill" style="width:${pct}%;background:${STATUS_COLOR[cp.current_status]}"></div></div>
        <div class="readout">${level == null ? "--" : level.toFixed(0)}<span class="unit"> cm</span></div>
      </div>`;
    card.onclick = () => selectChokePoint(cp.id);
    list.appendChild(card);
  });
}

// ---- Reports queue ---------------------------------------------------------
function renderReports(reports) {
  const list = document.getElementById("report-list");
  if (!reports.length) {
    list.innerHTML = '<div class="empty">No citizen reports yet.</div>';
    return;
  }
  // Unresolved first, newest first.
  reports.sort((a, b) => {
    if ((a.status === "resolved") !== (b.status === "resolved"))
      return a.status === "resolved" ? 1 : -1;
    return new Date(b.created_at) - new Date(a.created_at);
  });
  list.innerHTML = "";
  reports.forEach((r) => {
    const el = document.createElement("div");
    el.className = "report";
    el.innerHTML = `
      <div class="r-desc">${escapeHtml(r.description)}</div>
      <div class="r-meta">
        <span class="r-badge ${r.status}">${r.status}</span>
        ${r.request_monitoring ? '<span class="r-monitor">⚑ monitoring requested</span>' : ""}
        ${safePhotoLink(r.photo_url)}
        <span>${r.lat.toFixed(4)}, ${r.lng.toFixed(4)}</span>
      </div>
      <div class="actions">
        <button class="act" data-verify="${r.id}" ${r.status !== "unverified" ? "disabled" : ""}>Verify</button>
        <button class="act" data-resolve="${r.id}" ${r.status === "resolved" ? "disabled" : ""}>Resolve</button>
      </div>`;
    list.appendChild(el);
  });
  list.querySelectorAll("[data-verify]").forEach((b) =>
    (b.onclick = () => patchReport(b.dataset.verify, "verify"))
  );
  list.querySelectorAll("[data-resolve]").forEach((b) =>
    (b.onclick = () => patchReport(b.dataset.resolve, "resolve"))
  );
}

async function patchReport(id, action) {
  try {
    await fetch(`${API_BASE}/api/reports/${id}/${action}`, { method: "PATCH" });
    refresh();
  } catch (err) {
    alert(`Could not ${action} report: ${err.message}`);
  }
}

// ---- Map markers -----------------------------------------------------------
function renderMap(chokePoints, reports) {
  const keep = new Set();

  chokePoints.forEach((cp) => {
    const id = `choke_point:${cp.id}`;
    keep.add(id);
    const color = STATUS_COLOR[cp.current_status];
    if (markers[id]) {
      markers[id].setStyle({ fillColor: color });
    } else {
      markers[id] = L.circleMarker([cp.lat, cp.lng], {
        radius: 9, color: "#fff", weight: 2, fillColor: color, fillOpacity: 0.95,
      })
        .addTo(map)
        .on("click", () => selectChokePoint(cp.id));
    }
    markers[id].bindTooltip(`${cp.name} — ${cp.current_status}`);
  });

  reports.forEach((r) => {
    const id = `report:${r.id}`;
    keep.add(id);
    const color = r.status === "resolved" ? "#2fb380" : "#7c93ff";
    if (markers[id]) {
      markers[id].setStyle({ fillColor: color });
    } else {
      markers[id] = L.circleMarker([r.lat, r.lng], {
        radius: 6, color: "#fff", weight: 1, fillColor: color, fillOpacity: 0.9,
      }).addTo(map);
    }
    markers[id].bindTooltip(`Report: ${r.description} (${r.status})`);
  });

  // Drop markers whose entity disappeared.
  Object.keys(markers).forEach((id) => {
    if (!keep.has(id)) {
      map.removeLayer(markers[id]);
      delete markers[id];
    }
  });
}

// ---- Overall status ribbon (the signature element) -------------------------
function updateOverall(chokePoints) {
  let worst = "normal";
  chokePoints.forEach((cp) => {
    if (STATUS_RANK[cp.current_status] > STATUS_RANK[worst]) worst = cp.current_status;
  });
  const ribbon = document.getElementById("ribbon");
  ribbon.className = `status-${worst}`;
  const overall = document.getElementById("overall");
  overall.className = `overall status-${worst}`;
  overall.textContent =
    worst === "normal" ? "All Normal" : worst === "watch" ? "Watch — rising water" : "Critical — flooding";
}

// ---- Detail history chart --------------------------------------------------
function selectChokePoint(id) {
  selectedId = id;
  document.querySelectorAll(".cp").forEach((c) => c.classList.remove("selected"));
  loadHistory(id);
  refresh();
}

async function loadHistory(id) {
  const cp = chokePointCache[id];
  if (!cp) return;
  let rows;
  try {
    rows = await getJSON(`/api/flood/choke-points/${id}/history?limit=200`);
  } catch {
    return;
  }
  const detail = document.getElementById("detail");
  detail.innerHTML = `
    <div class="d-head">
      <span class="d-name">${escapeHtml(cp.name)}</span>
      <span class="d-coord">${cp.lat.toFixed(5)}, ${cp.lng.toFixed(5)}</span>
      <span class="d-thresholds">watch ≥ ${cp.watch_threshold_cm}cm · critical ≥ ${cp.critical_threshold_cm}cm</span>
    </div>
    <div id="chart-wrap"><canvas id="chart"></canvas></div>`;

  const labels = rows.map((r) => new Date(r.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
  const data = rows.map((r) => r.water_level_cm);

  if (chart) chart.destroy();
  chart = new Chart(document.getElementById("chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Water level (cm)", data, borderColor: "#3bc9db",
          backgroundColor: "rgba(59,201,219,0.12)", fill: true, tension: 0.3,
          pointRadius: 0, borderWidth: 2,
        },
        thresholdLine(cp.watch_threshold_cm, "#f4b740", labels.length),
        thresholdLine(cp.critical_threshold_cm, "#e4483b", labels.length),
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#8b9baa", maxTicksLimit: 8 }, grid: { color: "#22303f" } },
        y: { ticks: { color: "#8b9baa" }, grid: { color: "#22303f" }, title: { display: true, text: "cm", color: "#8b9baa" } },
      },
    },
  });
}

function thresholdLine(value, color, n) {
  return {
    label: "threshold", data: Array(n).fill(value),
    borderColor: color, borderDash: [5, 5], borderWidth: 1,
    pointRadius: 0, fill: false,
  };
}

// ---- utils -----------------------------------------------------------------
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// Resident-submitted URL -- only render it as a link if it's actually http(s),
// so a report can't smuggle a javascript: URI into an official's dashboard.
function safePhotoLink(url) {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return "";
    return `<a class="r-photo" href="${escapeHtml(parsed.href)}" target="_blank" rel="noopener noreferrer">📷 photo</a>`;
  } catch {
    return "";
  }
}

// ---- boot ------------------------------------------------------------------
initMap();
refresh();
setInterval(refresh, REFRESH_MS);
