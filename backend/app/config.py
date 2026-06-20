"""Application configuration."""
from __future__ import annotations

import os


class Settings:
    """Runtime settings, overridable via environment variables."""

    # Upstream BBWS Bengawan Solo hydrology API
    BBWS_API_URL: str = os.getenv(
        "BBWS_API_URL", "https://hidrologi.bbws-bsolo.net/api/last_data"
    )
    # Seconds to cache the upstream response (avoid hammering the source)
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "60"))
    # HTTP timeout when calling upstream
    HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "20"))

    # CORS origins allowed to call this API (comma separated, "*" for all)
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

    # Directory holding DEM GeoTIFFs used for inundation modelling.
    # If a DEM for a station is not found, a synthetic demo DEM is used.
    DEM_DIR: str = os.getenv(
        "DEM_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", "sample_data"),
    )


settings = Settings()
