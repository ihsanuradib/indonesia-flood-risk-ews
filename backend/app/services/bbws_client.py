"""Client + normalizer for the BBWS Bengawan Solo hydrology API.

The upstream `last_data` endpoint returns a flat list of heterogeneous
station records (TMA water level, CH rainfall, Klimatologi). This module
fetches, caches and normalizes them into a consistent `Station` schema and
exposes a GeoJSON FeatureCollection builder for the web map.
"""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from ..config import settings
from ..models import Station
from . import siaga

_cache: dict[str, Any] = {"ts": 0.0, "data": None}


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        s = str(value).strip()
        if s == "" or s.lower() == "null" or s == "-":
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_latlng(latlng: Any) -> Optional[tuple[float, float]]:
    if not latlng or str(latlng).lower() == "null":
        return None
    try:
        lat_s, lon_s = str(latlng).split(",")
        lat, lon = float(lat_s.strip()), float(lon_s.strip())
        # Sanity check for Indonesia / Java region
        if -12 < lat < 7 and 94 < lon < 142:
            return lat, lon
    except (ValueError, AttributeError):
        return None
    return None


def normalize(raw: dict[str, Any]) -> Optional[Station]:
    """Normalize a single upstream record into a Station, or None if invalid."""
    coords = _parse_latlng(raw.get("latlng"))
    if coords is None:
        return None
    lat, lon = coords

    tipe = (raw.get("tipe") or "").strip()
    wse_m: Optional[float] = None
    debit = _to_float(raw.get("debit_m3perdetik"))
    hijau = _to_float(raw.get("level_siaga_hijau_meter"))
    kuning = _to_float(raw.get("level_siaga_kuning_meter"))
    merah = _to_float(raw.get("level_siaga_merah_meter"))

    if tipe == "TMA":
        elev_cm = _to_float(raw.get("elevasi_cm"))
        wse_m = elev_cm / 100.0 if elev_cm is not None else None
        level = siaga.classify_tma(wse_m, hijau, kuning, merah)
    elif tipe in ("CH", "Klimatologi"):
        level = siaga.classify_rain(_to_float(raw.get("curah_hujan_mm")))
    else:
        level = 0

    label, color = siaga.level_meta(level)

    return Station(
        pos_id=str(raw.get("pos_id")),
        name=raw.get("nama_pos") or "Tanpa Nama",
        code=raw.get("kode_pos"),
        instansi=raw.get("instansi"),
        tipe=tipe or "Lainnya",
        wilayah=raw.get("wilayah"),
        das=None if str(raw.get("das")).lower() == "null" else raw.get("das"),
        lat=lat,
        lon=lon,
        tma_lokal_cm=_to_float(raw.get("tma_lokal_cm")),
        water_surface_elev_m=wse_m,
        debit_m3s=debit,
        siaga_hijau_m=hijau,
        siaga_kuning_m=kuning,
        siaga_merah_m=merah,
        curah_hujan_mm=_to_float(raw.get("curah_hujan_mm")),
        temperature=_to_float(raw.get("temperature")),
        humidity=_to_float(raw.get("humidity")),
        siaga_level=level,
        siaga_label=label,
        siaga_color=color,
        last_sampling=raw.get("last_sampling"),
        battery=_to_float(raw.get("battery")),
        signal_quality=raw.get("signal_quality"),
    )


async def fetch_raw() -> list[dict[str, Any]]:
    """Fetch raw records from upstream, with a short in-memory cache."""
    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < settings.CACHE_TTL:
        return _cache["data"]

    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        resp = await client.get(settings.BBWS_API_URL)
        resp.raise_for_status()
        data = resp.json()

    _cache["data"] = data
    _cache["ts"] = now
    return data


async def get_stations() -> list[Station]:
    raw = await fetch_raw()
    stations = [normalize(r) for r in raw]
    return [s for s in stations if s is not None]


def to_geojson(stations: list[Station]) -> dict[str, Any]:
    features = []
    for s in stations:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
                "properties": s.model_dump(exclude={"lat", "lon"}),
            }
        )
    return {"type": "FeatureCollection", "features": features}
