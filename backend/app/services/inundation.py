"""Flood inundation engine.

Three methods, tried in order of fidelity:

  1. **DEM bathtub** — if a real DEM GeoTIFF for the station is available
     (`sample_data/<pos_id>.tif`), classify cells with ground elevation <= the
     water surface and keep the part hydraulically connected to the gauge.
     Mirrors NOAA/USGS *rapid* Flood Inundation Mapping.

  2. **OSM river buffer** — fetch the real river/stream geometry near the gauge
     from OpenStreetMap (Overpass API) and buffer it by a width that grows with
     the water stage. The flooded footprint follows the *actual* river course,
     which is far more realistic than a synthetic channel and needs no DEM.

  3. **Synthetic DEM** — last-resort offline fallback (no network / no river
     found) so the pipeline always returns something for the demo.
"""
from __future__ import annotations

import math
import os
from typing import Any, Optional

import numpy as np

from ..config import settings

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


# ──────────────────────────────────────────────────────────────────────────
# 1. Real DEM (bathtub)
# ──────────────────────────────────────────────────────────────────────────
def _load_real_dem(pos_id: str):
    candidates = [f"{pos_id}.tif", f"{pos_id}.tiff", "dem.tif"]
    for name in candidates:
        path = os.path.normpath(os.path.join(settings.DEM_DIR, name))
        if os.path.exists(path):
            try:
                import rasterio
                with rasterio.open(path) as ds:
                    arr = ds.read(1).astype("float32")
                    arr = np.where(arr == ds.nodata, np.nan, arr)
                    return arr, ds.transform, ds.crs, name
            except Exception:
                return None
    return None


def _connected_to_gauge(mask: np.ndarray, gauge_rc: tuple[int, int]) -> np.ndarray:
    try:
        from scipy import ndimage
    except Exception:
        return mask
    labels, n = ndimage.label(mask)
    if n == 0:
        return mask
    gr, gc = gauge_rc
    gr = min(max(gr, 0), mask.shape[0] - 1)
    gc = min(max(gc, 0), mask.shape[1] - 1)
    target = labels[gr, gc]
    if target == 0:
        best, best_d = 0, 1e18
        for lab in range(1, n + 1):
            ys, xs = np.where(labels == lab)
            d = ((ys.mean() - gr) ** 2 + (xs.mean() - gc) ** 2)
            if d < best_d:
                best, best_d = lab, d
        target = best
    return labels == target


def _dem_inundation(pos_id, lat, lon, wse, real):
    arr, transform, crs, source = real
    from rasterio import features
    from rasterio.warp import transform_geom

    mask = np.where(np.isnan(arr), False, arr <= wse)
    inv = ~transform
    col, row = inv * (lon, lat)
    mask = _connected_to_gauge(mask, (int(row), int(col)))

    shapes = features.shapes(mask.astype("uint8"), mask=mask, transform=transform)
    geoms = [g for g, v in shapes if v == 1]
    out = []
    for g in geoms:
        out.append(transform_geom(crs, "EPSG:4326", g) if crs and crs.to_epsg() != 4326 else g)
    px_w = abs(transform.a) * 111320 * math.cos(math.radians(lat))
    px_h = abs(transform.e) * 110540
    area_km2 = mask.sum() * px_w * px_h / 1e6
    return {
        "geojson": {"type": "FeatureCollection",
                    "features": [{"type": "Feature", "geometry": g, "properties": {}} for g in out]},
        "flooded_area_km2": round(area_km2, 4),
        "method": "bathtub on supplied DEM (connected component)",
        "dem_source": source,
    }


# ──────────────────────────────────────────────────────────────────────────
# 2. OSM river buffer
# ──────────────────────────────────────────────────────────────────────────
def _fetch_osm_rivers(lat, lon, radius_m=5000):
    """Return nearby waterways as dicts: {coords:[(lon,lat)], name, kind}."""
    import httpx
    query = (
        "[out:json][timeout:25];"
        f'(way["waterway"~"river|canal|stream"](around:{radius_m},{lat},{lon}););'
        "out tags geom;"
    )
    for url in (OVERPASS_URL, "https://overpass.kumi.systems/api/interpreter"):
        try:
            r = httpx.post(url, data={"data": query}, timeout=30)
            r.raise_for_status()
            elements = r.json().get("elements", [])
        except Exception:
            continue
        ways = []
        for e in elements:
            if e.get("type") == "way" and e.get("geometry"):
                tags = e.get("tags") or {}
                ways.append({
                    "coords": [(g["lon"], g["lat"]) for g in e["geometry"]],
                    "name": tags.get("name"),
                    "kind": tags.get("waterway", "stream"),
                })
        if ways:
            return ways
    return []


def _stage_halfwidth_m(wse: float, anchor: float, merah: Optional[float]) -> float:
    """Map water-surface elevation to a flooded half-width (metres each bank).

    Anchored to siaga thresholds: roughly channel-only at low flow, widening to
    a broad floodplain at / beyond the red (Awas) threshold.
    """
    bottom = anchor                      # green (Waspada) ~ bankfull level
    top = merah if merah else anchor + 2.0
    span = (top - bottom) if top > bottom else 1.0
    frac = (wse - bottom) / span         # 0 at green, 1 at red
    frac = max(0.0, min(1.4, frac))
    return 20.0 + frac * 480.0           # ~20 m channel → ~700 m extreme


def _select_main_river(ways, lat, lon):
    """Pick the main waterway the gauge sits on (nearest, rivers preferred),
    then all same-named segments within 8 km to span the river course."""
    if not ways:
        return []
    k = 111320.0 * math.cos(math.radians(lat))

    def dmin(coords):
        return min(math.hypot((lo - lon) * k, (la - lat) * 110540.0) for lo, la in coords)

    best, best_score = None, 1e18
    for w in ways:
        w["_d"] = dmin(w["coords"])
        bonus = 400 if w["kind"] == "river" else 200 if w["kind"] == "canal" else 0
        score = w["_d"] - bonus
        if score < best_score:
            best_score, best = score, w
    if best is None:
        return []
    if best.get("name"):
        return [w for w in ways if w["name"] == best["name"] and w["_d"] < 8000]
    return [best]


def _river_buffer_inundation(lat, lon, wse, anchor, merah):
    ways = _select_main_river(_fetch_osm_rivers(lat, lon), lat, lon)
    if not ways:
        return None
    try:
        from shapely.geometry import LineString, mapping
        from shapely.ops import transform as shp_transform, unary_union
    except Exception:
        return None

    k = 111320.0 * math.cos(math.radians(lat))

    def inv(x, y, z=None):
        return (x / k, y / 110540.0)

    lines = []
    for w in ways:
        pts = [(lo * k, la * 110540.0) for lo, la in w["coords"]]
        if len(pts) >= 2:
            lines.append(LineString(pts))
    if not lines:
        return None

    half_w = _stage_halfwidth_m(wse, anchor, merah)
    poly = unary_union(lines).buffer(half_w, cap_style=2, join_style=1)
    if poly.is_empty:
        return None
    name = ways[0].get("name") or "terdekat"
    return {
        "geojson": {"type": "FeatureCollection",
                    "features": [{"type": "Feature",
                                  "geometry": mapping(shp_transform(inv, poly)),
                                  "properties": {}}]},
        "flooded_area_km2": round(poly.area / 1e6, 4),
        "method": f"OSM river buffer · {half_w:.0f} m/tepi (Sungai {name})",
        "dem_source": "OpenStreetMap waterways (Overpass)",
    }


# ──────────────────────────────────────────────────────────────────────────
# 3. Synthetic fallback
# ──────────────────────────────────────────────────────────────────────────
def _synthetic_inundation(lat, lon, wse, anchor):
    size, half_deg = 320, 0.025
    lats = np.linspace(lat + half_deg, lat - half_deg, size)
    lons = np.linspace(lon - half_deg, lon + half_deg, size)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    rows = np.arange(size)
    channel_col = (size / 2) + (size * 0.18) * np.sin(rows / size * 2 * math.pi)
    col_idx = np.tile(np.arange(size), (size, 1))
    dist_px = np.abs(col_idx - channel_col[:, None])
    bed = anchor - 6.0
    elev = bed + (dist_px / size) * 28.0 + np.linspace(2.0, -2.0, size)[:, None]
    mask = elev <= wse

    try:
        from skimage import measure
        contours = measure.find_contours(mask.astype(float), 0.5)
        polys = []
        for c in contours:
            if len(c) < 4:
                continue
            ring = []
            for r, cc in c:
                ri = min(max(int(round(r)), 0), size - 1)
                ci = min(max(int(round(cc)), 0), size - 1)
                ring.append([float(lon_grid[ri, ci]), float(lat_grid[ri, ci])])
            ring.append(ring[0])
            polys.append([ring])
        geom = {"type": "MultiPolygon", "coordinates": polys}
    except Exception:
        geom = {"type": "MultiPolygon", "coordinates": []}

    px = (2 * half_deg / (size - 1))
    px_w = px * 111320 * math.cos(math.radians(lat))
    px_h = px * 110540
    area_km2 = float(mask.sum()) * px_w * px_h / 1e6
    return {
        "geojson": {"type": "FeatureCollection",
                    "features": [{"type": "Feature", "geometry": geom, "properties": {}}]},
        "flooded_area_km2": round(area_km2, 4),
        "method": "bathtub on synthetic valley DEM (fallback)",
        "dem_source": "synthetic demo DEM",
    }


def compute_inundation(pos_id, lat, lon, water_surface_elev_m, anchor_elev_m, merah_elev_m=None):
    """Return inundation GeoJSON + stats, choosing the best available method."""
    real = _load_real_dem(pos_id)
    if real is not None:
        result = _dem_inundation(pos_id, lat, lon, water_surface_elev_m, real)
    else:
        result = _river_buffer_inundation(
            lat, lon, water_surface_elev_m, anchor_elev_m, merah_elev_m)
        if result is None:
            result = _synthetic_inundation(lat, lon, water_surface_elev_m, anchor_elev_m)
    result["water_surface_elev_m"] = water_surface_elev_m
    return result
