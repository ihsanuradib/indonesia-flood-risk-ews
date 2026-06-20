/* ── Runtime configuration ─────────────────────────────────────────────
 * API_BASE:
 *   - Set to your deployed FastAPI URL (e.g. "https://your-app.onrender.com")
 *     to get LIVE data + server-side flood inundation modelling.
 *   - Leave empty ("") for pure GitHub Pages mode: the app reads the static
 *     snapshot in data/stations.geojson (refreshed by GitHub Actions) and runs
 *     a lightweight client-side inundation demo.
 * ---------------------------------------------------------------------- */
window.APP_CONFIG = {
  API_BASE: "",                       // e.g. "https://bengawan-flood-ews.onrender.com"
  SNAPSHOT_URL: "data/stations.geojson",
  MAP_CENTER: [-7.55, 111.3],         // DAS Bengawan Solo
  MAP_ZOOM: 9,
  REFRESH_MS: 5 * 60 * 1000,          // auto-refresh interval (5 min)
};
