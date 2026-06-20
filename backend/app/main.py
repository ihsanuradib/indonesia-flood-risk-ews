"""FastAPI entry point for the Indonesia Flood Risk EWS WebGIS backend."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routers import inundation, stations

app = FastAPI(
    title="Indonesia Flood Risk EWS API",
    description=(
        "Backend WebGIS untuk Early Warning System banjir DAS Bengawan Solo. "
        "Menyediakan data stasiun (TMA/curah hujan) ter-normalisasi dan model "
        "genangan banjir (flood inundation) berbasis metode HAND/bathtub."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stations.router)
app.include_router(inundation.router)


@app.get("/")
def root():
    return JSONResponse(
        {
            "name": "Indonesia Flood Risk EWS API",
            "version": "1.0.0",
            "endpoints": [
                "/api/stations",
                "/api/stations/summary",
                "/api/stations/{pos_id}",
                "/api/inundation (POST)",
                "/docs",
            ],
        }
    )


@app.get("/health")
def health():
    return {"status": "ok"}
