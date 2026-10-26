from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.contracts import DashboardSummary

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard(request: Request) -> DashboardSummary:
    return DashboardSummary(**request.app.state.case_service.dashboard())


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    try:
        with request.app.state.case_service.database.connection() as connection:
            connection.execute("SELECT 1").fetchone()
    except Exception:
        return {"status": "degraded", "service": "parallax-api"}
    return {"status": "ok", "service": "parallax-api"}


@router.get("/version")
def version() -> dict[str, object]:
    return {
        "api_version": "0.2.0",
        "forensic_engine_version": "0.1.0",
        "modules": {
            "image": ["EXIF metadata", "timestamp consistency", "JPEG ELA", "ORB copy-move candidates"],
            "video": ["sampled frame sequence", "near duplicates", "transition leads"],
            "audio": ["WAV waveform", "spectrogram", "energy and clipping leads"],
            "custody": ["SHA-256 re-hash", "hash-chained audit verification"],
        },
    }
