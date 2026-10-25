from __future__ import annotations

import hashlib
import os
import stat
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile

from app.evidence.validation import DetectedMedia, EvidenceValidationError, validate_upload_metadata


class EvidenceStorageError(RuntimeError):
    """Raised for safe, recoverable evidence-storage failures."""


@dataclass(frozen=True)
class StoredEvidence:
    evidence_id: str
    original_filename: str
    storage_key: str
    media_type: str
    mime_type: str
    size_bytes: int
    sha256: str


class EvidenceStore:
    chunk_size = 1024 * 1024

    def __init__(self, originals_dir: Path, max_upload_bytes: int) -> None:
        self.originals_dir = originals_dir.resolve()
        self.max_upload_bytes = max_upload_bytes
        self.originals_dir.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, storage_key: str) -> Path:
        destination = (self.originals_dir / storage_key).resolve()
        try:
            destination.relative_to(self.originals_dir)
        except ValueError as exc:
            raise EvidenceStorageError("Invalid evidence storage path.") from exc
        return destination

    def persist(self, upload: UploadFile) -> StoredEvidence:
        """Persist a request-spooled upload before any forensic processing.

        FastAPI has already placed the multipart body in an UploadFile-backed
        temporary file. Reading that backing file directly keeps hashing and
        atomic placement deterministic; long-running media analysis is handled
        separately by a later worker phase.
        """
        header = upload.file.read(4096)
        upload.file.seek(0)
        safe_name, detected = validate_upload_metadata(upload.filename, upload.content_type, header)

        evidence_id = str(uuid.uuid4())
        date_partition = datetime.now(UTC).strftime("%Y/%m/%d")
        suffix = Path(safe_name).suffix.lower()
        storage_key = f"{date_partition}/{evidence_id}{suffix}"
        destination = self._safe_path(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256()
        total_bytes = 0
        try:
            # Evidence IDs are UUIDs and the final path is opened exclusively. This
            # avoids platform-specific rename behavior while still ensuring no
            # existing original can be overwritten.
            with open(destination, "xb") as output:
                while chunk := upload.file.read(self.chunk_size):
                    total_bytes += len(chunk)
                    if total_bytes > self.max_upload_bytes:
                        raise EvidenceValidationError(
                            f"Evidence exceeds the {self.max_upload_bytes // (1024 * 1024)} MB upload limit."
                        )
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            # Read-only after a complete, fsynced write. Derived artifacts are stored elsewhere.
            os.chmod(destination, stat.S_IREAD)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            upload.file.close()

        if total_bytes == 0:
            destination.unlink(missing_ok=True)
            raise EvidenceValidationError("Empty files cannot be accepted as evidence.")

        return StoredEvidence(
            evidence_id=evidence_id,
            original_filename=safe_name,
            storage_key=storage_key,
            media_type=detected.media_type,
            mime_type=detected.mime_type,
            size_bytes=total_bytes,
            sha256=digest.hexdigest(),
        )

    def original_path(self, storage_key: str) -> Path:
        path = self._safe_path(storage_key)
        if not path.is_file():
            raise EvidenceStorageError("The original evidence file is unavailable.")
        return path

    def sha256_original(self, storage_key: str) -> str:
        """Re-hash stored original bytes without exposing a writable handle."""
        digest = hashlib.sha256()
        with self.original_path(storage_key).open("rb") as source:
            while chunk := source.read(self.chunk_size):
                digest.update(chunk)
        return digest.hexdigest()
