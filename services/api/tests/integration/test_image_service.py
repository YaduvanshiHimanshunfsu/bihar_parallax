from __future__ import annotations

import io
import tempfile

from PIL import Image, ImageDraw
from starlette.datastructures import Headers, UploadFile

from app.core.config import Settings
from app.db.database import Database
from app.evidence.artifacts import DerivedArtifactStore
from app.evidence.storage import EvidenceStore
from app.schemas.contracts import CaseCreate
from app.services.cases import CaseService
from app.services.image_analysis import ImageAnalysisService


def test_image_analysis_stores_heatmap_separately_from_original(settings: Settings) -> None:
    database = Database(settings.database_path)
    service = CaseService(database)
    evidence_store = EvidenceStore(settings.originals_dir, settings.max_upload_bytes)
    image_service = ImageAnalysisService(service, evidence_store, DerivedArtifactStore(settings.derived_dir))
    case = service.create_case(CaseCreate(reference="CYB-IMG-01", title="Image analysis"), actor="pytest")

    source = Image.new("RGB", (100, 80), "#1d4c5d")
    ImageDraw.Draw(source).rectangle((50, 20, 86, 60), fill="#e0ae45")
    serialized = io.BytesIO()
    source.save(serialized, format="JPEG", quality=95)
    backing_file = tempfile.SpooledTemporaryFile(max_size=1024 * 1024)
    backing_file.write(serialized.getvalue())
    backing_file.seek(0)
    upload = UploadFile(file=backing_file, filename="scene.jpg", headers=Headers({"content-type": "image/jpeg"}))
    stored = evidence_store.persist(upload)
    evidence = service.add_evidence(case.id, stored, actor="pytest")

    analysis = image_service.analyse(evidence.id, actor="pytest")
    assert analysis.module == "image.metadata_ela"
    assert analysis.artifacts[0].artifact_type == "image.ela.heatmap"
    detail = service.get_evidence_detail(evidence.id)
    assert detail.analyses[0].findings
    assert list(settings.derived_dir.rglob("*.png"))
    assert list(settings.originals_dir.rglob("*.jpg"))
