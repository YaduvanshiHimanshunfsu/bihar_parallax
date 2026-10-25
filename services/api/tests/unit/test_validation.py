from __future__ import annotations

import pytest

from app.evidence.validation import EvidenceValidationError, detect_media, validate_upload_metadata


def test_detects_supported_media_signatures() -> None:
    assert detect_media(b"\x89PNG\r\n\x1a\nrest").mime_type == "image/png"
    assert detect_media(b"RIFFxxxxWAVErest").mime_type == "audio/wav"
    assert detect_media(b"\x00\x00\x00\x18ftypisomrest").mime_type == "video/mp4"


def test_rejects_traversal_and_signature_mismatch() -> None:
    with pytest.raises(EvidenceValidationError):
        validate_upload_metadata("../../proof.png", "image/png", b"\xff\xd8\xff\xe0")

    with pytest.raises(EvidenceValidationError):
        validate_upload_metadata("proof.jpg", "image/png", b"\xff\xd8\xff\xe0")
