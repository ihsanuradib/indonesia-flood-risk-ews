"""Station endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..services import bbws_client

router = APIRouter(prefix="/api", tags=["stations"])


@router.get("/stations")
async def list_stations(
    tipe: str | None = Query(None, description="Filter: TMA | CH | Klimatologi"),
    wilayah: str | None = Query(None, description="Filter: hulu | madiun | hilir"),
    min_siaga: int = Query(0, ge=0, le=3, description="Minimum siaga level"),
):
    """Return monitoring stations as a GeoJSON FeatureCollection."""
    try:
        stations = await bbws_client.get_stations()
    except Exception as exc:  # upstream failure
        raise HTTPException(status_code=502, detail=f"Upstream BBWS error: {exc}")

    if tipe:
        stations = [s for s in stations if s.tipe.lower() == tipe.lower()]
    if wilayah:
        stations = [s for s in stations if (s.wilayah or "").lower() == wilayah.lower()]
    if min_siaga:
        stations = [s for s in stations if s.siaga_level >= min_siaga]

    return bbws_client.to_geojson(stations)


@router.get("/stations/summary")
async def summary():
    """Aggregate counts useful for the dashboard header."""
    stations = await bbws_client.get_stations()
    by_type: dict[str, int] = {}
    by_siaga = {0: 0, 1: 0, 2: 0, 3: 0}
    for s in stations:
        by_type[s.tipe] = by_type.get(s.tipe, 0) + 1
        by_siaga[s.siaga_level] += 1
    return {
        "total": len(stations),
        "by_type": by_type,
        "by_siaga": by_siaga,
        "alerts": [
            {"pos_id": s.pos_id, "name": s.name, "level": s.siaga_label, "wilayah": s.wilayah}
            for s in stations
            if s.siaga_level >= 1
        ],
    }


@router.get("/stations/{pos_id}")
async def get_station(pos_id: str):
    stations = await bbws_client.get_stations()
    for s in stations:
        if s.pos_id == pos_id:
            return s
    raise HTTPException(status_code=404, detail="Station not found")
