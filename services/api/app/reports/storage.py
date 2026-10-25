from __future__ import annotations

import hashlib
import os
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredReport:
    report_id: str
    report_format: str
    storage_key: str
    sha256: str


class ReportStore:
    """Write immutable generated reports outside original-evidence storage."""

    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir.resolve()
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def persist(self, case_id: str, report_format: str, payload: bytes) -> StoredReport:
        if report_format not in {"json", "html", "pdf"}:
            raise ValueError("Unsupported report format.")
        if not payload:
            raise ValueError("A report cannot be empty.")
        report_id = str(uuid.uuid4())
        storage_key = f"{case_id}/{report_id}.{report_format}"
        destination = (self.reports_dir / storage_key).resolve()
        try:
            destination.relative_to(self.reports_dir)
        except ValueError as exc:
            raise ValueError("Invalid report storage path.") from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(destination, stat.S_IREAD)
        return StoredReport(
            report_id=report_id,
            report_format=report_format,
            storage_key=storage_key,
            sha256=hashlib.sha256(payload).hexdigest(),
        )
