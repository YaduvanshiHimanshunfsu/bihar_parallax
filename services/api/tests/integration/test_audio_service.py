from __future__ import annotations

import tempfile
import wave

import numpy as np
from starlette.datastructures import Headers, UploadFile

from app.core.config import Settings
from app.db.database import Database
from app.evidence.artifacts import DerivedArtifactStore
from app.evidence.storage import EvidenceStore
from app.schemas.contracts import CaseCreate
from app.services.audio_analysis import AudioAnalysisService
from app.services.cases import CaseService


def make_wav(path) -> None:
    sample_rate = 8_000
    signal = (0.35 * np.sin(2 * np.pi * 300 * np.arange(sample_rate * 3) / sample_rate) * np.iinfo(np.int16).max).astype(np.int16)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(signal.tobytes())


def test_audio_analysis_keeps_original_separate_from_derived_visual(settings: Settings, tmp_path) -> None:
    database = Database(settings.database_path)
    service = CaseService(database)
    evidence_store = EvidenceStore(settings.originals_dir, settings.max_upload_bytes)
    audio_service = AudioAnalysisService(service, evidence_store, DerivedArtifactStore(settings.derived_dir))
    case = service.create_case(CaseCreate(reference="CYB-AUD-01", title="Audio signal review"), actor="pytest")
    source_path = tmp_path / "recording.wav"
    make_wav(source_path)

    backing_file = tempfile.SpooledTemporaryFile(max_size=1024 * 1024)
    backing_file.write(source_path.read_bytes())
    backing_file.seek(0)
    upload = UploadFile(file=backing_file, filename="recording.wav", headers=Headers({"content-type": "audio/wav"}))
    stored = evidence_store.persist(upload)
    evidence = service.add_evidence(case.id, stored, actor="pytest")

    analysis = audio_service.analyse(evidence.id, actor="pytest")

    assert analysis.module == "audio.waveform_spectral"
    assert analysis.artifacts[0].artifact_type == "audio.waveform_spectrogram"
    assert service.get_evidence_detail(evidence.id).analyses[0].findings
    assert list(settings.derived_dir.rglob("*.png"))
    assert list(settings.originals_dir.rglob("*.wav"))
