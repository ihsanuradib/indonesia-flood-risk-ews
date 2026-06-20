"""Flood inundation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import InundationRequest
from ..services import bbws_client, inundation

router = APIRouter(prefix="/api", tags=["inundation"])


@router.post("/inundation")
async def model_inundation(req: InundationRequest):
    """Model flood extent for a TMA station at its current (or given) stage."""
    stations = await bbws_client.get_stations()
    station = next((s for s in stations if s.pos_id == req.pos_id), None)
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")
    if station.tipe != "TMA":
        raise HTTPException(status_code=400, detail="Inundation only available for TMA stations")

    wse = req.water_surface_elev_m
    if wse is None:
        wse = station.water_surface_elev_m
    if wse is None:
        raise HTTPException(status_code=400, detail="No water-surface elevation available")

    # anchor for synthetic DEM = green siaga threshold (or current WSE)
    anchor = station.siaga_hijau_m or station.water_surface_elev_m or wse

    result = inundation.compute_inundation(
        pos_id=station.pos_id,
        lat=station.lat,
        lon=station.lon,
        water_surface_elev_m=float(wse),
        anchor_elev_m=float(anchor),
        merah_elev_m=station.siaga_merah_m,
    )
    result["pos_id"] = station.pos_id
    return result
