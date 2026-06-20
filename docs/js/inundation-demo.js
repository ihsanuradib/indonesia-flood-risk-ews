/* Client-side flood inundation (GitHub Pages / static mode, no backend).
 *
 * Fetches the REAL river the gauge sits on from OpenStreetMap (Overpass API),
 * picks the nearest main waterway, and builds a flood ribbon along it whose
 * width scales with the water-surface elevation. No external geometry library
 * needed (manual perpendicular-offset buffer) so it is robust on GitHub Pages.
 * Falls back to a synthetic band only if Overpass is unreachable.
 */
window.InundationDemo = (function () {
  const HALF_DEG = 0.025, N = 90;
  const cache = {};
  const ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
  ];

  function halfWidthMeters(wse, anchor, merah) {
    const bottom = anchor;                 // green (Waspada) ~ bankfull
    const top = merah || (anchor + 2.0);
    const span = top > bottom ? top - bottom : 1.0;
    let frac = (wse - bottom) / span;      // 0 at green, 1 at red
    frac = Math.max(0, Math.min(1.4, frac));
    return 20 + frac * 480;                // ~20 m channel -> ~700 m per bank
  }

  async function fetchWays(lat, lon, radius) {
    const key = lat.toFixed(4) + "," + lon.toFixed(4);
    if (cache[key]) return cache[key];
    const q = `[out:json][timeout:20];(way["waterway"~"river|canal|stream"](around:${radius},${lat},${lon}););out tags geom;`;
    const body = "data=" + encodeURIComponent(q);

    // Race all Overpass mirrors; first OK response wins, others aborted.
    const tryOne = async (url) => {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 12000);
      try {
        const r = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body, signal: ctrl.signal,
        });
        if (!r.ok) throw new Error("status " + r.status);
        return await r.json();
      } finally { clearTimeout(timer); }
    };

    let j;
    try { j = await Promise.any(ENDPOINTS.map(tryOne)); }
    catch (e) { return []; }

    const ways = (j.elements || [])
      .filter(e => e.geometry && e.geometry.length >= 2)
      .map(e => ({
        coords: e.geometry.map(g => [g.lon, g.lat]),
        name: (e.tags && e.tags.name) || null,
        kind: (e.tags && e.tags.waterway) || "stream",
      }));
    if (ways.length) cache[key] = ways;
    return ways;
  }

  function distM(a, b, lat0) {
    const k = 111320 * Math.cos(lat0 * Math.PI / 180);
    return Math.hypot((a[0] - b[0]) * k, (a[1] - b[1]) * 110540);
  }

  // Pick the main river the gauge sits on: nearest waterway (rivers preferred),
  // then all same-named segments within 8 km (to span the whole river course).
  function selectMainRiver(ways, lat, lon) {
    if (!ways.length) return [];
    const g = [lon, lat];
    let best = null, bestScore = 1e18;
    for (const w of ways) {
      let d = 1e18;
      for (const p of w.coords) { const dd = distM(g, p, lat); if (dd < d) d = dd; }
      w._d = d;
      const bonus = w.kind === "river" ? 400 : w.kind === "canal" ? 200 : 0;
      const score = d - bonus;
      if (score < bestScore) { bestScore = score; best = w; }
    }
    if (!best) return [];
    if (best.name) return ways.filter(w => w.name === best.name && w._d < 8000);
    return [best];
  }

  // Build a polygon ribbon by offsetting the line +/- halfM along local normals.
  function ribbon(coords, halfM, lat0) {
    const k = 111320 * Math.cos(lat0 * Math.PI / 180);
    const xy = coords.map(([lo, la]) => [lo * k, la * 110540]);
    const n = xy.length, normals = [];
    for (let i = 0; i < n; i++) {
      let dx, dy;
      if (i === 0) { dx = xy[1][0] - xy[0][0]; dy = xy[1][1] - xy[0][1]; }
      else if (i === n - 1) { dx = xy[n - 1][0] - xy[n - 2][0]; dy = xy[n - 1][1] - xy[n - 2][1]; }
      else { dx = xy[i + 1][0] - xy[i - 1][0]; dy = xy[i + 1][1] - xy[i - 1][1]; }
      const L = Math.hypot(dx, dy) || 1;
      normals.push([-dy / L, dx / L]);
    }
    const left = [], right = [];
    for (let i = 0; i < n; i++) {
      left.push([xy[i][0] + normals[i][0] * halfM, xy[i][1] + normals[i][1] * halfM]);
      right.push([xy[i][0] - normals[i][0] * halfM, xy[i][1] - normals[i][1] * halfM]);
    }
    const ringXY = left.concat(right.reverse()); ringXY.push(ringXY[0]);
    let a = 0;
    for (let i = 0; i < ringXY.length - 1; i++)
      a += ringXY[i][0] * ringXY[i + 1][1] - ringXY[i + 1][0] * ringXY[i][1];
    return { ring: ringXY.map(([x, y]) => [x / k, y / 110540]), area: Math.abs(a) / 2 };
  }

  async function generate(lat, lon, wse, anchor, merah) {
    const halfM = halfWidthMeters(wse, anchor, merah);
    let ways = [];
    try { ways = await fetchWays(lat, lon, 5000); } catch (e) {}
    const sel = selectMainRiver(ways, lat, lon);
    if (sel.length) {
      const label = `OSM river buffer \u00b7 ${halfM.toFixed(0)} m/tepi (Sungai ${sel[0].name || "terdekat"})`;
      const src = "OpenStreetMap waterways (Overpass)";

      // Preferred: Turf buffer + dissolve -> one clean polygon, no gaps at
      // meanders or where OSM splits the river into separate ways.
      if (typeof turf !== "undefined") {
        try {
          const ml = turf.multiLineString(sel.map(w => w.coords));
          const buf = turf.buffer(ml, halfM / 1000, { units: "kilometers" });
          if (buf && buf.geometry) {
            return {
              geojson: { type: "FeatureCollection", features: [buf] },
              flooded_area_km2: Math.round(turf.area(buf) / 1e6 * 1000) / 1000,
              method: label, dem_source: src,
            };
          }
        } catch (e) { /* fall through to manual ribbons */ }
      }

      // Fallback: manual offset ribbons (may show minor gaps on sharp bends).
      const polys = []; let area = 0;
      for (const w of sel) { const rb = ribbon(w.coords, halfM, lat); polys.push([rb.ring]); area += rb.area; }
      return {
        geojson: { type: "FeatureCollection", features: [
          { type: "Feature", geometry: { type: "MultiPolygon", coordinates: polys }, properties: {} }] },
        flooded_area_km2: Math.round(area / 1e6 * 1000) / 1000,
        method: label + " [ribbon]", dem_source: src,
      };
    }
    return synthetic(lat, lon, wse, anchor);
  }

  function synthetic(lat, lon, wse, anchor) {
    const bed = anchor - 6.0;
    const stage = Math.max(0, wse - bed);
    const halfWidthDeg = Math.min(HALF_DEG, (stage / 28.0) * (2 * HALF_DEG));
    if (halfWidthDeg <= 0) {
      return { geojson: { type: "FeatureCollection", features: [] }, flooded_area_km2: 0,
        method: "client demo (no flooding)", dem_source: "synthetic demo DEM" };
    }
    const left = [], right = [];
    for (let i = 0; i < N; i++) {
      const t = i / (N - 1);
      const plat = lat + HALF_DEG - t * 2 * HALF_DEG;
      const clon = lon + 0.18 * HALF_DEG * 2 * Math.sin(t * 2 * Math.PI);
      left.push([clon - halfWidthDeg, plat]);
      right.push([clon + halfWidthDeg, plat]);
    }
    const ring = left.concat(right.reverse()); ring.push(ring[0]);
    const widthKm = 2 * halfWidthDeg * 111.32 * Math.cos(lat * Math.PI / 180);
    const area = widthKm * (2 * HALF_DEG * 110.54) * 0.62;
    return {
      geojson: { type: "FeatureCollection", features: [
        { type: "Feature", geometry: { type: "Polygon", coordinates: [ring] }, properties: {} }] },
      flooded_area_km2: Math.round(area * 1000) / 1000,
      method: "bathtub on synthetic valley DEM (fallback)",
      dem_source: "synthetic demo DEM",
    };
  }

  return { generate };
})();
