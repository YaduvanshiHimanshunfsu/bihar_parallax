from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    reference: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    title: str = Field(min_length=3, max_length=160)


class CaseSummary(BaseModel):
    id: str
    reference: str
    title: str
    evidence_count: int
    created_at: str
    updated_at: str


class EvidenceSummary(BaseModel):
    id: str
    original_filename: str
    media_type: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: str
    original_immutable: bool


class FindingSummary(BaseModel):
    id: str
    code: str
    severity: str
    title: str
    detail: str
    evidence: dict[str, Any]


class DerivedArtifactSummary(BaseModel):
    id: str
    artifact_type: str
    sha256: str


class AnalysisSummary(BaseModel):
    id: str
    module: str
    module_version: str
    status: str
    summary: dict[str, Any]
    created_at: str
    findings: list[FindingSummary]
    artifacts: list[DerivedArtifactSummary]


class ReportSummary(BaseModel):
    id: str
    report_format: str
    sha256: str
    created_at: str


class AssessmentSignalSummary(BaseModel):
    evidence_id: str
    module: str
    code: str
    severity: str
    title: str


class AssessmentSummary(BaseModel):
    id: str
    outcome: str
    reasons: list[str]
    signals: list[AssessmentSignalSummary]
    created_at: str


class AnalystNoteCreate(BaseModel):
    note: str = Field(min_length=3, max_length=4_000)
    disposition: str | None = Field(default=None, max_length=120)


class AnalystNote(BaseModel):
    id: str
    author: str
    note: str
    disposition: str | None
    created_at: str


class EvidenceDetail(EvidenceSummary):
    analyses: list[AnalysisSummary]


class IntegrityVerification(BaseModel):
    evidence_id: str
    expected_sha256: str
    computed_sha256: str
    matches: bool
    verified_at: str


class AuditEvent(BaseModel):
    id: int
    event_type: str
    actor: str
    details: dict[str, Any]
    created_at: str
    previous_event_hash: str | None = None
    event_hash: str | None = None


class AuditChainVerification(BaseModel):
    case_id: str
    chain_intact: bool
    total_events: int
    sealed_events: int
    legacy_unsealed_events: int
    invalid_event_id: int | None = None
    verification_note: str


class CaseDetail(CaseSummary):
    evidence: list[EvidenceSummary]
    audit_events: list[AuditEvent]
    reports: list[ReportSummary] = Field(default_factory=list)
    assessment: AssessmentSummary | None = None
    notes: list[AnalystNote] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    active_cases: int
    evidence_analysed: int
    needs_expert_review: int
    custody_integrity_percent: int
    recent_cases: list[CaseSummary]
