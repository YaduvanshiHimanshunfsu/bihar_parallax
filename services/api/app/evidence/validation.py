from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class EvidenceValidationError(ValueError):
    """Raised when a submitted artifact cannot safely enter evidence storage."""


@dataclass(frozen=True)
class DetectedMedia:
    media_type: str
    mime_type: str
    extensions: frozenset[str]


JPEG = DetectedMedia("image", "image/jpeg", frozenset({".jpg", ".jpeg"}))
PNG = DetectedMedia("image", "image/png", frozenset({".png"}))
WAV = DetectedMedia("audio", "audio/wav", frozenset({".wav"}))
MP3 = DetectedMedia("audio", "audio/mpeg", frozenset({".mp3"}))
MP4 = DetectedMedia("video", "video/mp4", frozenset({".mp4", ".m4v"}))
AVI = DetectedMedia("video", "video/x-msvideo", frozenset({".avi"}))
MKV = DetectedMedia("video", "video/x-matroska", frozenset({".mkv"}))


def safe_original_filename(filename: str | None) -> str:
    if not filename:
        raise EvidenceValidationError("An evidence file name is required.")
    safe_name = Path(filename).name.strip()
    if not safe_name or safe_name in {".", ".."}:
        raise EvidenceValidationError("The evidence file name is invalid.")
    if len(safe_name) > 180:
        raise EvidenceValidationError("The evidence file name is too long.")
    return safe_name


def detect_media(header: bytes) -> DetectedMedia:
    if header.startswith(b"\xff\xd8\xff"):
        return JPEG
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return WAV
    if header.startswith(b"RIFF") and header[8:12] == b"AVI ":
        return AVI
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return MP4
    if header.startswith(b"\x1aE\xdf\xa3"):
        return MKV
    if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0):
        return MP3
    raise EvidenceValidationError(
        "Unsupported or unverifiable file signature. Submit a JPEG, PNG, WAV, MP3, MP4, AVI, or MKV file."
    )


def validate_upload_metadata(filename: str | None, declared_content_type: str | None, header: bytes) -> tuple[str, DetectedMedia]:
    safe_name = safe_original_filename(filename)
    detected = detect_media(header)
    extension = Path(safe_name).suffix.lower()
    if extension not in detected.extensions:
        supported = ", ".join(sorted(detected.extensions))
        raise EvidenceValidationError(
            f"The extension '{extension or '[none]'}' does not match the detected {detected.mime_type} file signature. Expected: {supported}."
        )

    declared = (declared_content_type or "").split(";", 1)[0].strip().lower()
    neutral_types = {"", "application/octet-stream", "binary/octet-stream"}
    if declared not in neutral_types and declared != detected.mime_type:
        raise EvidenceValidationError(
            f"The browser declared '{declared}', but the file signature is '{detected.mime_type}'."
        )
    return safe_name, detected
