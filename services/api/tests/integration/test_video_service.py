from __future__ import annotations

import tempfile

import cv2
import numpy as np
from starlette.datastructures import Headers, UploadFile

from app.core.config import Settings
from app.db.database import Database
from app.evidence.artifacts import DerivedArtifactStore
from app.evidence.storage import EvidenceStore
from app.schemas.contracts import CaseCreate
from app.services.cases import CaseService
from app.services.video_analysis import VideoAnalysisService


def make_avi(path) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 5.0, (64, 48))
    assert writer.isOpened(), "The OpenCV test fixture could not create an AVI file."
    try:
        for index in range(10):
            frame = np.full((48, 64, 3), 30 if index < 5 else 220, dtype=np.uint8)
            writer.write(frame)
    finally:
        writer.release()


def test_video_analysis_keeps_original_separate_from_contact_sheet(settings: Settings, tmp_path) -> None:
    database = Database(settings.database_path)
    service = CaseService(database)
    evidence_store = EvidenceStore(settings.originals_dir, settings.max_upload_bytes)
    video_service = VideoAnalysisService(service, evidence_store, DerivedArtifactStore(settings.derived_dir))
    case = service.create_case(CaseCreate(reference="CYB-VID-01", title="Video sequence review"), actor="pytest")
    source_path = tmp_path / "sequence.avi"
    make_avi(source_path)

    backing_file = tempfile.SpooledTemporaryFile(max_size=1024 * 1024)
    backing_file.write(source_path.read_bytes())
    backing_file.seek(0)
    upload = UploadFile(file=backing_file, filename="sequence.avi", headers=Headers({"content-type": "video/x-msvideo"}))
    stored = evidence_store.persist(upload)
    evidence = service.add_evidence(case.id, stored, actor="pytest")

    analysis = video_service.analyse(evidence.id, actor="pytest")

    assert analysis.module == "video.frame_sequence"
    assert analysis.artifacts[0].artifact_type == "video.sampled_contact_sheet"
    detail = service.get_evidence_detail(evidence.id)
    assert detail.analyses[0].findings
    assert list(settings.derived_dir.rglob("*.png"))
    assert list(settings.originals_dir.rglob("*.avi"))
