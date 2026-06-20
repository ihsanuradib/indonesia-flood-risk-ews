/* Bengawan Solo Flood EWS — main app */
(function () {
  const cfg = window.APP_CONFIG;
  const hasBackend = !!cfg.API_BASE;
  let stations = [];          // array of GeoJSON features
  let markerLayer, floodLayer, selected = null, charts = {};

  /* ── Map ── */
  const map = L.map("map", { zoomControl: true }).setView(cfg.MAP_CENTER, cfg.MAP_ZOOM);
  const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    { attribution: "© OpenStreetMap", maxZoom: 19 }).addTo(map);
  const sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { attribution: "© Esri", maxZoom: 19 });
  const topo = L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    { attribution: "© OpenTopoMap", maxZoom: 17 });
  L.control.layers({ "Peta Jalan": osm, "Citra Satelit": sat, "Topografi": topo },
    null, { position: "bottomright" }).addTo(map);
  floodLayer = L.geoJSON(null, { style: { color: "#3b82f6", weight: 1, fillColor: "#3b82f6", fillOpacity: .42 } }).addTo(map);
  markerLayer = L.layerGroup().addTo(map);

  /* ── Data loading ── */
  async function loadStations() {
    showLoading(true);
    try {
      let fc;
      if (hasBackend) {
        const r = await fetch(`${cfg.API_BASE}/api/stations`);
        fc = await r.json();
      } else {
        const r = await fetch(cfg.SNAPSHOT_URL, { cache: "no-store" });
        fc = await r.json();
      }
      stations = fc.features || [];
      render();
      updateUpdated(fc.generated_at);
    } catch (e) {
      document.getElementById("alert-list").innerHTML =
        `<li class="muted">Gagal memuat data: ${e.message}</li>`;
    } finally { showLoading(false); }
  }

  /* ── Rendering ── */
  function filtered() {
    const t = document.getElementById("f-tipe").value;
    const w = document.getElementById("f-wilayah").value;
    const onlyAlert = document.getElementById("f-alert").checked;
    return stations.filter(f => {
      const p = f.properties;
      if (t && p.tipe !== t) return false;
      if (w && (p.wilayah || "") !== w) return false;
      if (onlyAlert && (p.siaga_level || 0) < 1) return false;
      return true;
    });
  }

  function render() {
    markerLayer.clearLayers();
    const data = filtered();
    data.forEach(f => {
      const p = f.properties;
      const [lon, lat] = f.geometry.coordinates;
      const isTMA = p.tipe === "TMA";
      const m = L.circleMarker([lat, lon], {
        radius: isTMA ? 8 : 6,
        color: "#0b1220", weight: 1.4,
        fillColor: p.siaga_color || "#2ecc71",
        fillOpacity: .95,
      });
      m.bindPopup(() => popupHtml(p), { maxWidth: 300 });
      m.on("popupopen", () => drawPopupChart(p));
      markerLayer.addLayer(m);
    });
    renderKpis();
    renderAlerts();
  }

  function popupHtml(p) {
    const badge = `<span class="pp-badge" style="background:${p.siaga_color}">${p.siaga_label}</span>`;
    let rows = "";
    if (p.tipe === "TMA") {
      rows = `
        <div>TMA lokal</div><b>${fmt(p.tma_lokal_cm)} cm</b>
        <div>Elevasi MA</div><b>${fmt(p.water_surface_elev_m)} m</b>
        <div>Debit</div><b>${fmt(p.debit_m3s)} m³/s</b>
        <div>Ambang merah</div><b>${fmt(p.siaga_merah_m)} m</b>`;
    } else {
      rows = `
        <div>Curah hujan</div><b>${fmt(p.curah_hujan_mm)} mm</b>
        ${p.temperature != null ? `<div>Suhu</div><b>${fmt(p.temperature)} °C</b>` : ""}
        ${p.humidity != null ? `<div>Lembap</div><b>${fmt(p.humidity)} %</b>` : ""}`;
    }
    const btn = p.tipe === "TMA"
      ? `<button class="pp-btn" onclick="window.__openInundation('${p.pos_id}')"><i class="fa-solid fa-water"></i> Model Genangan Banjir</button>` : "";
    return `
      <div class="pp-title">${p.name} ${badge}</div>
      <div class="pp-sub">${p.code || ""} · ${p.tipe} · ${cap(p.wilayah)} · DAS ${p.das || "—"}</div>
      <div class="pp-grid">${rows}</div>
      <canvas class="pp-canvas" id="chart-${p.pos_id}" height="110"></canvas>
      ${btn}`;
  }

  function drawPopupChart(p) {
    const el = document.getElementById(`chart-${p.pos_id}`);
    if (!el) return;
    if (charts[p.pos_id]) charts[p.pos_id].destroy();
    if (p.tipe === "TMA" && p.water_surface_elev_m != null) {
      charts[p.pos_id] = new Chart(el, {
        type: "bar",
        data: {
          labels: ["Muka Air", "Hijau", "Kuning", "Merah"],
          datasets: [{
            data: [p.water_surface_elev_m, p.siaga_hijau_m, p.siaga_kuning_m, p.siaga_merah_m],
            backgroundColor: [p.siaga_color, "#2ecc71", "#f1c40f", "#e74c3c"],
          }],
        },
        options: chartOpts("Elevasi (m)"),
      });
    } else {
      charts[p.pos_id] = new Chart(el, {
        type: "bar",
        data: { labels: ["Curah Hujan"], datasets: [{ data: [p.curah_hujan_mm || 0], backgroundColor: ["#4f8ef7"] }] },
        options: chartOpts("mm"),
      });
    }
  }
  function chartOpts(title) {
    return { responsive: true, plugins: { legend: { display: false }, title: { display: true, text: title, color: "#8aa0c6", font: { size: 10 } } },
      scales: { x: { ticks: { color: "#8aa0c6", font: { size: 9 } }, grid: { display: false } },
        y: { ticks: { color: "#8aa0c6", font: { size: 9 } }, grid: { color: "rgba(255,255,255,.06)" } } } };
  }

  /* ── KPIs & alerts ── */
  function renderKpis() {
    const total = stations.length;
    const alert = stations.filter(f => (f.properties.siaga_level || 0) >= 1).length;
    const tma = stations.filter(f => f.properties.tipe === "TMA").length;
    document.getElementById("kpi-total").textContent = total;
    document.getElementById("kpi-alert").textContent = alert;
    document.getElementById("kpi-tma").textContent = tma;
  }
  function renderAlerts() {
    const alerts = stations.filter(f => (f.properties.siaga_level || 0) >= 1)
      .sort((a, b) => b.properties.siaga_level - a.properties.siaga_level);
    const ul = document.getElementById("alert-list");
    if (!alerts.length) { ul.innerHTML = `<li class="muted">Tidak ada pos berstatus siaga 👍</li>`; return; }
    ul.innerHTML = alerts.map(f => {
      const p = f.properties, [lon, lat] = f.geometry.coordinates;
      return `<li onclick="window.__flyTo(${lat},${lon},'${p.pos_id}')">
        <span>${p.name}</span>
        <span class="lv" style="background:${p.siaga_color};color:#06121f">${p.siaga_label}</span></li>`;
    }).join("");
  }

  /* ── Inundation ── */
  window.__openInundation = function (posId) {
    const f = stations.find(s => s.properties.pos_id === posId);
    if (!f) return;
    selected = f.properties;
    const p = selected;
    document.getElementById("inundation-panel").classList.remove("hidden");
    document.getElementById("ip-name").textContent = p.name;
    document.getElementById("ip-debit").textContent = fmt(p.debit_m3s);
    const bed = (p.siaga_hijau_m || p.water_surface_elev_m || 0) - 6;
    const top = (p.siaga_merah_m || p.water_surface_elev_m || 0) + 2;
    const slider = document.getElementById("ip-slider");
    slider.min = 0; slider.max = 100;
    slider.value = pct(p.water_surface_elev_m, bed, top);
    slider._bed = bed; slider._top = top; slider._anchor = p.siaga_hijau_m || p.water_surface_elev_m;
    updateWseLabel();
    runInundation();
  };
  function updateWseLabel() {
    const s = document.getElementById("ip-slider");
    const wse = s._bed + (s.value / 100) * (s._top - s._bed);
    document.getElementById("ip-wse").textContent = wse.toFixed(2);
    return wse;
  }
  async function runInundation() {
    if (!selected) return;
    const wse = updateWseLabel();
    const s = document.getElementById("ip-slider");
    showLoading(true);
    let res;
    try {
      if (hasBackend) {
        const r = await fetch(`${cfg.API_BASE}/api/inundation`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pos_id: selected.pos_id, water_surface_elev_m: wse }),
        });
        res = await r.json();
      } else {
        res = await window.InundationDemo.generate(
          selected_lat(selected), selected_lon(selected), wse, s._anchor, selected.siaga_merah_m);
      }
    } catch (e) {
      res = await window.InundationDemo.generate(
        selected_lat(selected), selected_lon(selected), wse, s._anchor, selected.siaga_merah_m);
    }
    floodLayer.clearLayers();
    if (res.geojson) floodLayer.addData(res.geojson);
    document.getElementById("ip-area").textContent = res.flooded_area_km2 ?? "–";
    document.getElementById("ip-method").textContent = `${res.method} · sumber: ${res.dem_source}`;
    showLoading(false);
  }
  function selected_lat(p){ const f = stations.find(s=>s.properties.pos_id===p.pos_id); return f.geometry.coordinates[1]; }
  function selected_lon(p){ const f = stations.find(s=>s.properties.pos_id===p.pos_id); return f.geometry.coordinates[0]; }

  /* ── Fly to ── */
  window.__flyTo = function (lat, lon, posId) {
    map.flyTo([lat, lon], 12);
    markerLayer.eachLayer(l => { if (l.getLatLng && Math.abs(l.getLatLng().lat - lat) < 1e-6) l.openPopup(); });
  };

  /* ── Helpers ── */
  function fmt(v) { return v == null ? "–" : (Math.round(v * 100) / 100); }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : "—"; }
  function pct(v, a, b) { if (v == null) return 50; return Math.max(0, Math.min(100, ((v - a) / (b - a)) * 100)); }
  function showLoading(on) { document.getElementById("loading").classList.toggle("hidden", !on); }
  function updateUpdated(ts) {
    const d = ts ? new Date(ts) : new Date();
    document.getElementById("updated").textContent = "Diperbarui " + d.toLocaleTimeString("id-ID");
  }

  /* ── Events ── */
  ["f-tipe", "f-wilayah", "f-alert"].forEach(id =>
    document.getElementById(id).addEventListener("change", render));
  document.getElementById("ip-close").onclick = () => {
    document.getElementById("inundation-panel").classList.add("hidden");
    floodLayer.clearLayers(); selected = null;
  };
  document.getElementById("ip-slider").addEventListener("input", updateWseLabel);
  document.getElementById("ip-run").onclick = runInundation;
  document.getElementById("btn-about").onclick = () => document.getElementById("about").classList.remove("hidden");
  document.getElementById("about-close").onclick = () => document.getElementById("about").classList.add("hidden");

  /* ── Boot ── */
  loadStations();
  setInterval(loadStations, cfg.REFRESH_MS);
})();
