"""Siaga (flood alert level) classification logic.

For water-level (TMA) stations BBWS publishes three absolute elevation
thresholds (in metres): green (hijau / Siaga III - Waspada),
yellow (kuning / Siaga II), red (merah / Siaga I - Awas).

We compare the current water-surface elevation (elevasi_cm / 100) against
those thresholds and return a normalized level.
"""
from __future__ import annotations

from typing import Optional

# level -> (label, color)
LEVELS = {
    0: ("Aman", "#2ecc71"),      # green dot
    1: ("Waspada", "#f1c40f"),   # yellow
    2: ("Siaga", "#e67e22"),     # orange
    3: ("Awas", "#e74c3c"),      # red
}


def classify_tma(
    water_surface_elev_m: Optional[float],
    hijau: Optional[float],
    kuning: Optional[float],
    merah: Optional[float],
) -> int:
    """Return siaga level 0..3 for a water-level station."""
    if water_surface_elev_m is None:
        return 0
    if merah is not None and water_surface_elev_m >= merah:
        return 3
    if kuning is not None and water_surface_elev_m >= kuning:
        return 2
    if hijau is not None and water_surface_elev_m >= hijau:
        return 1
    return 0


def classify_rain(curah_hujan_mm: Optional[float]) -> int:
    """Rough rainfall intensity classification (per sampling interval, mm).

    Based on BMKG hourly rainfall categories adapted for alerting.
    """
    if curah_hujan_mm is None:
        return 0
    if curah_hujan_mm >= 20:
        return 3      # very heavy
    if curah_hujan_mm >= 10:
        return 2      # heavy
    if curah_hujan_mm >= 5:
        return 1      # moderate
    return 0


def level_meta(level: int) -> tuple[str, str]:
    return LEVELS.get(level, LEVELS[0])
