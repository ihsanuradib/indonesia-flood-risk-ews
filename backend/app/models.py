"""Pydantic models for API responses."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class Station(BaseModel):
    """Normalized monitoring station."""

    pos_id: str
    name: str
    code: Optional[str] = None
    instansi: Optional[str] = None
    tipe: str                      # TMA | CH | Klimatologi
    wilayah: Optional[str] = None  # hulu | madiun | hilir
    das: Optional[str] = None      # river basin / DAS
    lat: float
    lon: float

    # Water level (TMA) fields
    tma_lokal_cm: Optional[float] = None
    water_surface_elev_m: Optional[float] = None  # absolute elevation (m)
    debit_m3s: Optional[float] = None
    siaga_hijau_m: Optional[float] = None
    siaga_kuning_m: Optional[float] = None
    siaga_merah_m: Optional[float] = None

    # Rainfall (CH) / climate fields
    curah_hujan_mm: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None

    # Derived siaga classification
    siaga_level: int = 0           # 0 aman, 1 waspada, 2 siaga, 3 awas
    siaga_label: str = "Aman"
    siaga_color: str = "#2ecc71"

    # Metadata
    last_sampling: Optional[str] = None
    battery: Optional[float] = None
    signal_quality: Optional[str] = None


class InundationRequest(BaseModel):
    pos_id: str
    # Optional manual water-surface elevation override (m). If omitted the
    # station's current measured elevation is used.
    water_surface_elev_m: Optional[float] = None


class InundationResponse(BaseModel):
    pos_id: str
    water_surface_elev_m: float
    flooded_area_km2: float
    method: str
    dem_source: str
    geojson: dict[str, Any]
