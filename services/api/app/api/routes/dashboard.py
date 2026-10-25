from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.contracts import DashboardSummary

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard(request: Request) -> DashboardSummary:
    return DashboardSummary(**request.app.state.case_service.dashboard())


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "parallax-api"}
