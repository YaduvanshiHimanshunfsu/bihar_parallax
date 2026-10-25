from __future__ import annotations

import stat
import tempfile

import pytest
from starlette.datastructures import Headers, UploadFile

from app.core.config import Settings
from app.evidence.storage import EvidenceStore
from app.evidence.validation import EvidenceValidationError
from app.schemas.contracts import CaseCreate
from app.services.cases import CaseNotFoundError, CaseService
from app.services.integrity import IntegrityVerificationService

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def upload_file(name: str, payload: bytes, content_type: str) -> UploadFile:
    backing_file = tempfile.SpooledTemporaryFile(max_size=1024 * 1024)
    backing_file.write(payload)
    backing_file.seek(0)
    return UploadFile(file=backing_file, filename=name, headers=Headers({"content-type": content_type}))


def create_case(service: CaseService) -> dict:
    return service.create_case(
        CaseCreate(reference="CYB-2026-TEST-01", title="Test evidence intake"), actor="pytest"
    ).model_dump()


def test_intake_hashes_records_and_preserves_original(
    case_service: CaseService, evidence_store: EvidenceStore, settings: Settings
) -> None:
    case = create_case(case_service)
    stored = evidence_store.persist(upload_file("original.png", PNG_BYTES, "image/png"))
    evidence = case_service.add_evidence(case["id"], stored, actor="pytest")

    assert evidence.original_filename == "original.png"
    assert evidence.mime_type == "image/png"
    assert evidence.size_bytes == len(PNG_BYTES)
    assert evidence.original_immutable is True
    assert len(evidence.sha256) == 64

    stored_files = list(settings.originals_dir.rglob("*.png"))
    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == PNG_BYTES
    assert not (stored_files[0].stat().st_mode & stat.S_IWUSR)

    case_detail = case_service.get_case(case["id"])
    events = [event.event_type for event in case_detail.audit_events]
    assert "case.created" in events
    assert "evidence.intake.completed" in events


def test_rehash_verification_records_a_custody_event(
    case_service: CaseService, evidence_store: EvidenceStore
) -> None:
    case = create_case(case_service)
    stored = evidence_store.persist(upload_file("verified.png", PNG_BYTES, "image/png"))
    evidence = case_service.add_evidence(case["id"], stored, actor="pytest")

    verification = IntegrityVerificationService(case_service, evidence_store).verify(evidence.id, actor="pytest")

    assert verification.matches is True
    assert verification.computed_sha256 == evidence.sha256
    events = [event.event_type for event in case_service.get_case(case["id"]).audit_events]
    assert "evidence.integrity.verified" in events


def test_rejects_extension_that_does_not_match_signature(evidence_store: EvidenceStore) -> None:
    with pytest.raises(EvidenceValidationError, match="does not match"):
        evidence_store.persist(upload_file("mislabeled.png", JPEG_BYTES, "image/jpeg"))


def test_unknown_case_is_rejected_before_persisting_original(
    case_service: CaseService, settings: Settings
) -> None:
    with pytest.raises(CaseNotFoundError):
        case_service.get_case_summary("not-a-case")
    assert list(settings.originals_dir.rglob("*")) == []
