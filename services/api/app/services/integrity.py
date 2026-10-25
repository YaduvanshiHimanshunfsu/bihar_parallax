from __future__ import annotations

from app.db.database import utc_now
from app.evidence.storage import EvidenceStore
from app.schemas.contracts import IntegrityVerification
from app.services.cases import CaseNotFoundError, CaseService


class IntegrityVerificationService:
    """Re-hash an immutable original and record the outcome as a custody event."""

    def __init__(self, case_service: CaseService, evidence_store: EvidenceStore) -> None:
        self.case_service = case_service
        self.evidence_store = evidence_store

    def verify(self, evidence_id: str, actor: str) -> IntegrityVerification:
        with self.case_service.database.connection() as connection:
            evidence = connection.execute(
                "SELECT case_id, storage_key, sha256 FROM evidence_items WHERE id = ?", (evidence_id,)
            ).fetchone()
            if not evidence:
                raise CaseNotFoundError(evidence_id)
        computed = self.evidence_store.sha256_original(evidence["storage_key"])
        verified_at = utc_now()
        matches = computed == evidence["sha256"]
        with self.case_service.database.connection() as connection:
            self.case_service.database.add_audit_event(
                connection,
                event_type="evidence.integrity.verified",
                actor=actor,
                case_id=evidence["case_id"],
                evidence_id=evidence_id,
                details={"expected_sha256": evidence["sha256"], "computed_sha256": computed, "matches": matches},
            )
        return IntegrityVerification(
            evidence_id=evidence_id,
            expected_sha256=evidence["sha256"],
            computed_sha256=computed,
            matches=matches,
            verified_at=verified_at,
        )
