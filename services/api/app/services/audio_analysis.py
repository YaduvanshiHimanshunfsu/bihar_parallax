from __future__ import annotations

from app.evidence.artifacts import DerivedArtifactStore
from app.evidence.storage import EvidenceStore
from app.schemas.contracts import AnalysisSummary
from app.services.cases import CaseService
from forensic_engine.audio.analysis import analyse_audio


class AudioAnalysisService:
    """Runs local WAV integrity triage and stores a derived visual aid separately."""

    def __init__(self, case_service: CaseService, evidence_store: EvidenceStore, artifact_store: DerivedArtifactStore) -> None:
        self.case_service = case_service
        self.evidence_store = evidence_store
        self.artifact_store = artifact_store

    def analyse(self, evidence_id: str, actor: str) -> AnalysisSummary:
        storage_key, _ = self.case_service.get_evidence_storage_key(evidence_id)
        result = analyse_audio(self.evidence_store.original_path(storage_key))
        artifact = None
        if result.waveform_png:
            artifact = self.artifact_store.persist_bytes(
                evidence_id=evidence_id,
                artifact_type="audio.waveform_spectrogram",
                payload=result.waveform_png,
                suffix=".png",
            )
        return self.case_service.record_audio_analysis(evidence_id, result, artifact, actor)
