"""Offline Phase 1 smoke test: case creation, immutable intake, and audit record.

Run from the project root:
    python scripts/smoke_phase1.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from starlette.datastructures import Headers, UploadFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "services" / "api"))

from app.core.config import Settings  # noqa: E402
from app.db.database import Database  # noqa: E402
from app.evidence.storage import EvidenceStore  # noqa: E402
from app.schemas.contracts import CaseCreate  # noqa: E402
from app.services.cases import CaseService, DuplicateCaseError  # noqa: E402


def main() -> None:
    settings = Settings.from_environment()
    settings.create_directories()
    database = Database(settings.database_path)
    database.initialise()
    service = CaseService(database)
    store = EvidenceStore(settings.originals_dir, settings.max_upload_bytes)

    reference = "DEMO-PHASE1-001"
    try:
        case = service.create_case(
            CaseCreate(reference=reference, title="Phase 1 evidence-intake smoke test"), actor="smoke-test"
        )
    except DuplicateCaseError:
        case = next(item for item in service.list_cases() if item.reference == reference)

    sample = b"\x89PNG\r\n\x1a\n" + b"Parallax phase 1 demo evidence"
    backing_file = tempfile.SpooledTemporaryFile(max_size=1024 * 1024)
    backing_file.write(sample)
    backing_file.seek(0)
    upload = UploadFile(file=backing_file, filename="phase1-demo.png", headers=Headers({"content-type": "image/png"}))
    stored = store.persist(upload)
    evidence = service.add_evidence(case.id, stored, actor="smoke-test")
    print(f"Case: {case.reference}")
    print(f"Evidence ID: {evidence.id}")
    print(f"SHA-256: {evidence.sha256}")
    print(f"Original stored read-only: {settings.originals_dir / stored.storage_key}")


if __name__ == "__main__":
    main()
