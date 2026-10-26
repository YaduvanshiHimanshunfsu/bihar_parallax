from __future__ import annotations

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes import cases, dashboard
from app.core.config import Settings
from app.db.database import Database
from app.evidence.artifacts import DerivedArtifactStore
from app.evidence.storage import EvidenceStore
from app.services.cases import CaseService
from app.services.image_analysis import ImageAnalysisService
from app.services.video_analysis import VideoAnalysisService
from app.services.audio_analysis import AudioAnalysisService
from app.services.reporting import ReportService
from app.reports.storage import ReportStore
from app.services.integrity import IntegrityVerificationService
from app.services.assessment import AssessmentService


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings.from_environment()
    active_settings.create_directories()
    database = Database(active_settings.database_path)
    database.initialise()
    store = EvidenceStore(active_settings.originals_dir, active_settings.max_upload_bytes)
    artifact_store = DerivedArtifactStore(active_settings.derived_dir)
    report_store = ReportStore(active_settings.reports_dir)

    app = FastAPI(
        title="Parallax Evidence Integrity API",
        version="0.1.0",
        description="Evidence-first integrity analysis, custody verification, and human-review workflows.",
    )
    app.state.settings = active_settings
    app.state.case_service = CaseService(database)
    app.state.evidence_store = store
    app.state.artifact_store = artifact_store
    app.state.image_analysis_service = ImageAnalysisService(app.state.case_service, store, artifact_store)
    app.state.video_analysis_service = VideoAnalysisService(app.state.case_service, store, artifact_store)
    app.state.audio_analysis_service = AudioAnalysisService(app.state.case_service, store, artifact_store)
    app.state.report_store = report_store
    app.state.report_service = ReportService(app.state.case_service, report_store)
    app.state.integrity_verification_service = IntegrityVerificationService(app.state.case_service, store)
    app.state.assessment_service = AssessmentService(app.state.case_service)
    configured_origins = [
        origin.strip()
        for origin in os.getenv("PARALLAX_CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Analyst-ID"],
    )
    app.include_router(dashboard.router, prefix="/api/v1")
    app.include_router(cases.router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    def serve_dashboard() -> FileResponse:
        return web_file("index.html")

    @app.get("/{asset_name}.css", include_in_schema=False)
    def serve_styles(asset_name: str) -> FileResponse:
        return web_file(f"{asset_name}.css")

    @app.get("/{asset_name}.js", include_in_schema=False)
    def serve_script(asset_name: str) -> FileResponse:
        return web_file(f"{asset_name}.js")

    def web_file(filename: str) -> FileResponse:
        path = (active_settings.web_dir / filename).resolve()
        try:
            path.relative_to(active_settings.web_dir.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Web asset not found.") from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Web asset not found.")
        return FileResponse(path)

    return app


app = create_app()
