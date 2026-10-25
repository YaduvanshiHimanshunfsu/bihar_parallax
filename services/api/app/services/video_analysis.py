from __future__ import annotations

from app.evidence.artifacts import DerivedArtifactStore
from app.evidence.storage import EvidenceStore
from app.schemas.contracts import AnalysisSummary
from app.services.cases import CaseService
from forensic_engine.video.analysis import analyse_video


class VideoAnalysisService:
    """Runs bounded CCTV/video triage and persists derived review artifacts only."""

    def __init__(self, case_service: CaseService, evidence_store: EvidenceStore, artifact_store: DerivedArtifactStore) -> None:
        self.case_service = case_service
        self.evidence_store = evidence_store
        self.artifact_store = artifact_store

    def analyse(self, evidence_id: str, actor: str) -> AnalysisSummary:
        storage_key, _ = self.case_service.get_evidence_storage_key(evidence_id)
        result = analyse_video(self.evidence_store.original_path(storage_key))
        artifact = None
        if result.contact_sheet_png:
            artifact = self.artifact_store.persist_bytes(
                evidence_id=evidence_id,
                artifact_type="video.sampled_contact_sheet",
                payload=result.contact_sheet_png,
                suffix=".png",
            )
        return self.case_service.record_video_analysis(evidence_id, result, artifact, actor)
