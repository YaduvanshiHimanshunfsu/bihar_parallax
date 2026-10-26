from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from app.db.database import Database, utc_now
from app.evidence.storage import StoredEvidence
from app.evidence.artifacts import StoredArtifact
from app.reports.storage import StoredReport
from app.schemas.contracts import (
    AnalysisSummary,
    AnalystNote,
    AnalystNoteCreate,
    AssessmentSignalSummary,
    AssessmentSummary,
    AuditEvent,
    AuditChainVerification,
    CaseCreate,
    CaseDetail,
    CaseSummary,
    DerivedArtifactSummary,
    EvidenceDetail,
    EvidenceSummary,
    FindingSummary,
    ReportSummary,
)
from forensic_engine.fusion.assessment import CaseAssessment
from forensic_engine.image.analysis import ImageAnalysisResult
from forensic_engine.video.analysis import VideoAnalysisResult
from forensic_engine.audio.analysis import AudioAnalysisResult


class CaseNotFoundError(LookupError):
    pass


class DuplicateCaseError(ValueError):
    pass


class CaseService:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _summary(row: sqlite3.Row) -> CaseSummary:
        return CaseSummary(
            id=row["id"],
            reference=row["reference"],
            title=row["title"],
            evidence_count=row["evidence_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create_case(self, payload: CaseCreate, actor: str) -> CaseSummary:
        case_id = str(uuid.uuid4())
        now = utc_now()
        reference = payload.reference.strip().upper()
        title = payload.title.strip()
        try:
            with self.database.connection() as connection:
                connection.execute(
                    "INSERT INTO cases(id, reference, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (case_id, reference, title, now, now),
                )
                self.database.add_audit_event(
                    connection,
                    event_type="case.created",
                    actor=actor,
                    case_id=case_id,
                    details={"reference": reference, "title": title},
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateCaseError(f"A case with reference '{reference}' already exists.") from exc
        return self.get_case_summary(case_id)

    def get_case_summary(self, case_id: str) -> CaseSummary:
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT c.*, COUNT(e.id) AS evidence_count
                FROM cases c LEFT JOIN evidence_items e ON e.case_id = c.id
                WHERE c.id = ? GROUP BY c.id
                """,
                (case_id,),
            ).fetchone()
        if not row:
            raise CaseNotFoundError(case_id)
        return self._summary(row)

    def list_cases(self, limit: int = 50) -> list[CaseSummary]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT c.*, COUNT(e.id) AS evidence_count
                FROM cases c LEFT JOIN evidence_items e ON e.case_id = c.id
                GROUP BY c.id ORDER BY c.updated_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._summary(row) for row in rows]

    def get_case(self, case_id: str) -> CaseDetail:
        summary = self.get_case_summary(case_id)
        with self.database.connection() as connection:
            evidence_rows = connection.execute(
                "SELECT * FROM evidence_items WHERE case_id = ? ORDER BY created_at DESC",
                (case_id,),
            ).fetchall()
            audit_rows = connection.execute(
                "SELECT * FROM audit_events WHERE case_id = ? ORDER BY id DESC",
                (case_id,),
            ).fetchall()
            report_rows = connection.execute(
                "SELECT * FROM reports WHERE case_id = ? ORDER BY created_at DESC",
                (case_id,),
            ).fetchall()
            assessment_row = connection.execute(
                "SELECT * FROM case_assessments WHERE case_id = ? ORDER BY created_at DESC LIMIT 1",
                (case_id,),
            ).fetchone()
            note_rows = connection.execute(
                "SELECT * FROM analyst_notes WHERE case_id = ? ORDER BY created_at DESC", (case_id,)
            ).fetchall()
        return CaseDetail(
            **summary.model_dump(),
            evidence=[
                EvidenceSummary(
                    id=row["id"], original_filename=row["original_filename"], media_type=row["media_type"],
                    mime_type=row["mime_type"], size_bytes=row["size_bytes"], sha256=row["sha256"],
                    created_at=row["created_at"], original_immutable=bool(row["original_immutable"]),
                )
                for row in evidence_rows
            ],
            audit_events=[
                AuditEvent(
                    id=row["id"], event_type=row["event_type"], actor=row["actor"],
                    details=json.loads(row["details_json"]), created_at=row["created_at"],
                    previous_event_hash=row["previous_event_hash"], event_hash=row["event_hash"],
                )
                for row in audit_rows
            ],
            reports=[
                ReportSummary(
                    id=row["id"], report_format=row["report_format"], sha256=row["sha256"], created_at=row["created_at"]
                )
                for row in report_rows
            ],
            assessment=(
                AssessmentSummary(
                    id=assessment_row["id"],
                    outcome=assessment_row["outcome"],
                    reasons=json.loads(assessment_row["reasons_json"]),
                    signals=[AssessmentSignalSummary(**signal) for signal in json.loads(assessment_row["signals_json"])],
                    created_at=assessment_row["created_at"],
                )
                if assessment_row
                else None
            ),
            notes=[
                AnalystNote(
                    id=row["id"], author=row["author"], note=row["note"],
                    disposition=row["disposition"], created_at=row["created_at"],
                )
                for row in note_rows
            ],
        )

    def add_analyst_note(self, case_id: str, payload: AnalystNoteCreate, actor: str) -> AnalystNote:
        self.get_case_summary(case_id)
        note_id = str(uuid.uuid4())
        created_at = utc_now()
        note = payload.note.strip()
        disposition = payload.disposition.strip() if payload.disposition else None
        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO analyst_notes(id, case_id, author, note, disposition, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (note_id, case_id, actor, note, disposition, created_at),
            )
            connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (created_at, case_id))
            self.database.add_audit_event(
                connection,
                event_type="case.analyst_note.recorded",
                actor=actor,
                case_id=case_id,
                details={"note_id": note_id, "disposition": disposition, "note_length": len(note)},
            )
        return AnalystNote(id=note_id, author=actor, note=note, disposition=disposition, created_at=created_at)

    def add_evidence(self, case_id: str, stored: StoredEvidence, actor: str) -> EvidenceSummary:
        self.get_case_summary(case_id)
        now = utc_now()
        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO evidence_items(
                    id, case_id, original_filename, storage_key, media_type, mime_type,
                    size_bytes, sha256, created_at, original_immutable
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    stored.evidence_id, case_id, stored.original_filename, stored.storage_key,
                    stored.media_type, stored.mime_type, stored.size_bytes, stored.sha256, now,
                ),
            )
            connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, case_id))
            self.database.add_audit_event(
                connection,
                event_type="evidence.intake.completed",
                actor=actor,
                case_id=case_id,
                evidence_id=stored.evidence_id,
                details={
                    "filename": stored.original_filename,
                    "media_type": stored.media_type,
                    "mime_type": stored.mime_type,
                    "size_bytes": stored.size_bytes,
                    "sha256": stored.sha256,
                    "original_immutable": True,
                },
            )
        return EvidenceSummary(
            id=stored.evidence_id, original_filename=stored.original_filename, media_type=stored.media_type,
            mime_type=stored.mime_type, size_bytes=stored.size_bytes, sha256=stored.sha256,
            created_at=now, original_immutable=True,
        )

    def dashboard(self) -> dict[str, Any]:
        with self.database.connection() as connection:
            active_cases = connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
            evidence_analysed = connection.execute("SELECT COUNT(*) FROM evidence_items").fetchone()[0]
            needs_expert_review = connection.execute(
                """
                SELECT COUNT(DISTINCT analysis_runs.evidence_id)
                FROM findings JOIN analysis_runs ON analysis_runs.id = findings.analysis_id
                WHERE findings.severity = 'review'
                """
            ).fetchone()[0]
        return {
            "active_cases": active_cases,
            "evidence_analysed": evidence_analysed,
            "needs_expert_review": needs_expert_review,
            "custody_integrity_percent": 100,
            "recent_cases": self.list_cases(limit=5),
        }

    def get_evidence_storage_key(self, evidence_id: str) -> tuple[str, str]:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT storage_key, original_filename FROM evidence_items WHERE id = ?", (evidence_id,)
            ).fetchone()
        if not row:
            raise CaseNotFoundError(evidence_id)
        return row["storage_key"], row["original_filename"]

    def verify_audit_chain(self, case_id: str) -> AuditChainVerification:
        self.get_case_summary(case_id)
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events WHERE case_id = ? ORDER BY id ASC", (case_id,)
            ).fetchall()

        last_sealed_hash: str | None = None
        sealed_events = 0
        legacy_events = 0
        for row in rows:
            event_hash = row["event_hash"]
            previous_hash = row["previous_event_hash"]
            if event_hash is None and previous_hash is None:
                legacy_events += 1
                continue
            if not event_hash or previous_hash != last_sealed_hash:
                return AuditChainVerification(
                    case_id=case_id,
                    chain_intact=False,
                    total_events=len(rows),
                    sealed_events=sealed_events,
                    legacy_unsealed_events=legacy_events,
                    invalid_event_id=row["id"],
                    verification_note="An audit event has an incomplete or unexpected chain link. Preserve the database and escalate for review.",
                )
            expected_hash = self.database.audit_event_hash(
                case_id=row["case_id"],
                evidence_id=row["evidence_id"],
                event_type=row["event_type"],
                actor=row["actor"],
                details=json.loads(row["details_json"]),
                created_at=row["created_at"],
                previous_event_hash=previous_hash,
            )
            if event_hash != expected_hash:
                return AuditChainVerification(
                    case_id=case_id,
                    chain_intact=False,
                    total_events=len(rows),
                    sealed_events=sealed_events,
                    legacy_unsealed_events=legacy_events,
                    invalid_event_id=row["id"],
                    verification_note="An audit event hash does not match its stored event data. Preserve the database and escalate for review.",
                )
            sealed_events += 1
            last_sealed_hash = event_hash

        if sealed_events == 0:
            note = "This case contains only pre-chain legacy audit events, so no hash-chain verification is available for its existing history."
            intact = False
        elif legacy_events:
            note = "The sealed portion of the audit chain is intact. Earlier legacy events pre-date local chain sealing and remain unverified."
            intact = True
        else:
            note = "All recorded case audit events are linked and their hashes match the current stored event data."
            intact = True
        return AuditChainVerification(
            case_id=case_id,
            chain_intact=intact,
            total_events=len(rows),
            sealed_events=sealed_events,
            legacy_unsealed_events=legacy_events,
            verification_note=note,
        )

    def get_evidence_detail(self, evidence_id: str) -> EvidenceDetail:
        with self.database.connection() as connection:
            evidence = connection.execute("SELECT * FROM evidence_items WHERE id = ?", (evidence_id,)).fetchone()
            if not evidence:
                raise CaseNotFoundError(evidence_id)
            analysis_rows = connection.execute(
                "SELECT * FROM analysis_runs WHERE evidence_id = ? ORDER BY created_at DESC", (evidence_id,)
            ).fetchall()

            analyses: list[AnalysisSummary] = []
            for analysis in analysis_rows:
                finding_rows = connection.execute(
                    "SELECT * FROM findings WHERE analysis_id = ? ORDER BY created_at ASC", (analysis["id"],)
                ).fetchall()
                artifact_rows = connection.execute(
                    """
                    SELECT d.* FROM derived_artifacts d
                    JOIN analysis_artifacts aa ON aa.artifact_id = d.id
                    WHERE aa.analysis_id = ?
                    """,
                    (analysis["id"],),
                ).fetchall()
                analyses.append(
                    AnalysisSummary(
                        id=analysis["id"], module=analysis["module"], module_version=analysis["module_version"],
                        status=analysis["status"], summary=json.loads(analysis["summary_json"]),
                        created_at=analysis["created_at"],
                        findings=[
                            FindingSummary(
                                id=row["id"], code=row["code"], severity=row["severity"], title=row["title"],
                                detail=row["detail"], evidence=json.loads(row["evidence_json"]),
                            )
                            for row in finding_rows
                        ],
                        artifacts=[
                            DerivedArtifactSummary(id=row["id"], artifact_type=row["artifact_type"], sha256=row["sha256"])
                            for row in artifact_rows
                        ],
                    )
                )
        return EvidenceDetail(
            id=evidence["id"], original_filename=evidence["original_filename"], media_type=evidence["media_type"],
            mime_type=evidence["mime_type"], size_bytes=evidence["size_bytes"], sha256=evidence["sha256"],
            created_at=evidence["created_at"], original_immutable=bool(evidence["original_immutable"]), analyses=analyses,
        )

    def record_image_analysis(
        self,
        evidence_id: str,
        result: ImageAnalysisResult,
        artifact: StoredArtifact | None,
        actor: str,
    ) -> AnalysisSummary:
        with self.database.connection() as connection:
            evidence = connection.execute("SELECT case_id FROM evidence_items WHERE id = ?", (evidence_id,)).fetchone()
            if not evidence:
                raise CaseNotFoundError(evidence_id)
            analysis_id = str(uuid.uuid4())
            now = utc_now()
            summary = {
                "image_format": result.image_format,
                "width": result.width,
                "height": result.height,
                "color_mode": result.color_mode,
                "metadata": result.metadata,
                "ela_metrics": result.ela_metrics,
            }
            connection.execute(
                """
                INSERT INTO analysis_runs(id, evidence_id, module, module_version, status, parameters_json, summary_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id, evidence_id, "image.metadata_ela", "0.2.0", "completed",
                    json.dumps({"jpeg_recompression_quality": 90, "copy_move_detector": "ORB", "copy_move_max_dimension": 1600}, sort_keys=True), json.dumps(summary, sort_keys=True), now,
                ),
            )
            for finding in result.findings:
                connection.execute(
                    """
                    INSERT INTO findings(id, analysis_id, code, severity, title, detail, evidence_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()), analysis_id, finding.code, finding.severity, finding.title,
                        finding.detail, json.dumps(finding.evidence, sort_keys=True), now,
                    ),
                )
            if artifact:
                connection.execute(
                    """
                    INSERT INTO derived_artifacts(id, evidence_id, artifact_type, storage_key, sha256, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (artifact.artifact_id, evidence_id, artifact.artifact_type, artifact.storage_key, artifact.sha256, now),
                )
                connection.execute(
                    "INSERT INTO analysis_artifacts(analysis_id, artifact_id) VALUES (?, ?)",
                    (analysis_id, artifact.artifact_id),
                )
            connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, evidence["case_id"]))
            self.database.add_audit_event(
                connection,
                event_type="analysis.image_integrity_review.completed",
                actor=actor,
                case_id=evidence["case_id"],
                evidence_id=evidence_id,
                details={"analysis_id": analysis_id, "finding_count": len(result.findings), "artifact_id": artifact.artifact_id if artifact else None},
            )
        return self.get_evidence_detail(evidence_id).analyses[0]

    def get_artifact_storage_key(self, artifact_id: str) -> str:
        with self.database.connection() as connection:
            row = connection.execute("SELECT storage_key FROM derived_artifacts WHERE id = ?", (artifact_id,)).fetchone()
        if not row:
            raise CaseNotFoundError(artifact_id)
        return row["storage_key"]

    def record_reports(self, case_id: str, reports: list[StoredReport], actor: str) -> list[ReportSummary]:
        if not reports:
            raise ValueError("At least one generated report is required.")
        self.get_case_summary(case_id)
        now = utc_now()
        with self.database.connection() as connection:
            for report in reports:
                connection.execute(
                    """
                    INSERT INTO reports(id, case_id, report_format, storage_key, sha256, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (report.report_id, case_id, report.report_format, report.storage_key, report.sha256, now),
                )
            connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, case_id))
            self.database.add_audit_event(
                connection,
                event_type="report.dossier.generated",
                actor=actor,
                case_id=case_id,
                details={
                    "report_ids": [report.report_id for report in reports],
                    "formats": [report.report_format for report in reports],
                    "report_hashes": {report.report_format: report.sha256 for report in reports},
                },
            )
        return [
            ReportSummary(id=report.report_id, report_format=report.report_format, sha256=report.sha256, created_at=now)
            for report in reports
        ]

    def get_report_storage(self, report_id: str) -> tuple[str, str]:
        with self.database.connection() as connection:
            row = connection.execute("SELECT storage_key, report_format FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not row:
            raise CaseNotFoundError(report_id)
        return row["storage_key"], row["report_format"]

    def record_assessment(self, case_id: str, assessment: CaseAssessment, actor: str) -> AssessmentSummary:
        self.get_case_summary(case_id)
        assessment_id = str(uuid.uuid4())
        now = utc_now()
        signal_payload = [
            {
                "evidence_id": signal.evidence_id,
                "module": signal.module,
                "code": signal.code,
                "severity": signal.severity,
                "title": signal.title,
            }
            for signal in assessment.signals
        ]
        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO case_assessments(id, case_id, outcome, reasons_json, signals_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (assessment_id, case_id, assessment.outcome, json.dumps(assessment.reasons), json.dumps(signal_payload), now),
            )
            connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, case_id))
            self.database.add_audit_event(
                connection,
                event_type="case.assessment.generated",
                actor=actor,
                case_id=case_id,
                details={"assessment_id": assessment_id, "outcome": assessment.outcome, "signal_count": len(signal_payload)},
            )
        return AssessmentSummary(
            id=assessment_id,
            outcome=assessment.outcome,
            reasons=assessment.reasons,
            signals=[AssessmentSignalSummary(**signal) for signal in signal_payload],
            created_at=now,
        )

    def record_audio_analysis(
        self,
        evidence_id: str,
        result: AudioAnalysisResult,
        artifact: StoredArtifact | None,
        actor: str,
    ) -> AnalysisSummary:
        with self.database.connection() as connection:
            evidence = connection.execute("SELECT case_id FROM evidence_items WHERE id = ?", (evidence_id,)).fetchone()
            if not evidence:
                raise CaseNotFoundError(evidence_id)
            analysis_id = str(uuid.uuid4())
            now = utc_now()
            connection.execute(
                """
                INSERT INTO analysis_runs(id, evidence_id, module, module_version, status, parameters_json, summary_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id, evidence_id, "audio.waveform_spectral", "0.1.0", "completed",
                    json.dumps({"max_seconds": 600, "block_duration_target_seconds": 0.25}, sort_keys=True),
                    json.dumps(result.summary, sort_keys=True), now,
                ),
            )
            for finding in result.findings:
                connection.execute(
                    """
                    INSERT INTO findings(id, analysis_id, code, severity, title, detail, evidence_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()), analysis_id, finding.code, finding.severity, finding.title,
                        finding.detail, json.dumps(finding.evidence, sort_keys=True), now,
                    ),
                )
            if artifact:
                connection.execute(
                    """
                    INSERT INTO derived_artifacts(id, evidence_id, artifact_type, storage_key, sha256, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (artifact.artifact_id, evidence_id, artifact.artifact_type, artifact.storage_key, artifact.sha256, now),
                )
                connection.execute(
                    "INSERT INTO analysis_artifacts(analysis_id, artifact_id) VALUES (?, ?)",
                    (analysis_id, artifact.artifact_id),
                )
            connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, evidence["case_id"]))
            self.database.add_audit_event(
                connection,
                event_type="analysis.audio_waveform_spectral.completed",
                actor=actor,
                case_id=evidence["case_id"],
                evidence_id=evidence_id,
                details={"analysis_id": analysis_id, "finding_count": len(result.findings), "artifact_id": artifact.artifact_id if artifact else None},
            )
        return self.get_evidence_detail(evidence_id).analyses[0]

    def record_video_analysis(
        self,
        evidence_id: str,
        result: VideoAnalysisResult,
        artifact: StoredArtifact | None,
        actor: str,
    ) -> AnalysisSummary:
        with self.database.connection() as connection:
            evidence = connection.execute("SELECT case_id FROM evidence_items WHERE id = ?", (evidence_id,)).fetchone()
            if not evidence:
                raise CaseNotFoundError(evidence_id)
            analysis_id = str(uuid.uuid4())
            now = utc_now()
            connection.execute(
                """
                INSERT INTO analysis_runs(id, evidence_id, module, module_version, status, parameters_json, summary_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id, evidence_id, "video.frame_sequence", "0.1.0", "completed",
                    json.dumps({"max_samples": 300, "duplicate_difference_threshold": 0.8}, sort_keys=True),
                    json.dumps(result.summary, sort_keys=True), now,
                ),
            )
            for finding in result.findings:
                connection.execute(
                    """
                    INSERT INTO findings(id, analysis_id, code, severity, title, detail, evidence_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()), analysis_id, finding.code, finding.severity, finding.title,
                        finding.detail, json.dumps(finding.evidence, sort_keys=True), now,
                    ),
                )
            if artifact:
                connection.execute(
                    """
                    INSERT INTO derived_artifacts(id, evidence_id, artifact_type, storage_key, sha256, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (artifact.artifact_id, evidence_id, artifact.artifact_type, artifact.storage_key, artifact.sha256, now),
                )
                connection.execute(
                    "INSERT INTO analysis_artifacts(analysis_id, artifact_id) VALUES (?, ?)",
                    (analysis_id, artifact.artifact_id),
                )
            connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, evidence["case_id"]))
            self.database.add_audit_event(
                connection,
                event_type="analysis.video_frame_sequence.completed",
                actor=actor,
                case_id=evidence["case_id"],
                evidence_id=evidence_id,
                details={"analysis_id": analysis_id, "finding_count": len(result.findings), "artifact_id": artifact.artifact_id if artifact else None},
            )
        return self.get_evidence_detail(evidence_id).analyses[0]
