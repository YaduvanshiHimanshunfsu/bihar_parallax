from __future__ import annotations

import hashlib
import os
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredArtifact:
    artifact_id: str
    artifact_type: str
    storage_key: str
    sha256: str


class DerivedArtifactStore:
    """Store reproducible visual artifacts separately from immutable originals."""

    def __init__(self, derived_dir: Path) -> None:
        self.derived_dir = derived_dir.resolve()
        self.derived_dir.mkdir(parents=True, exist_ok=True)

    def persist_bytes(self, evidence_id: str, artifact_type: str, payload: bytes, suffix: str) -> StoredArtifact:
        if not payload:
            raise ValueError("A derived artifact cannot be empty.")
        artifact_id = str(uuid.uuid4())
        safe_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        storage_key = f"{evidence_id}/{artifact_id}{safe_suffix.lower()}"
        destination = (self.derived_dir / storage_key).resolve()
        try:
            destination.relative_to(self.derived_dir)
        except ValueError as exc:
            raise ValueError("Invalid derived-artifact storage path.") from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(destination, stat.S_IREAD)
        return StoredArtifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            storage_key=storage_key,
            sha256=hashlib.sha256(payload).hexdigest(),
        )
