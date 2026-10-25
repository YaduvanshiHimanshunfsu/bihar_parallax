from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Settings:
    """Filesystem settings kept explicit to protect original evidence paths."""

    project_root: Path
    data_root: Path
    database_path: Path
    originals_dir: Path
    derived_dir: Path
    reports_dir: Path
    web_dir: Path
    max_upload_bytes: int = 250 * 1024 * 1024

    @classmethod
    def from_environment(cls) -> "Settings":
        project_root = _project_root()
        data_root = Path(os.getenv("PARALLAX_DATA_DIR", project_root / "data")).resolve()
        max_upload_mb = int(os.getenv("ANALYSIS_MAX_UPLOAD_MB", "250"))
        return cls(
            project_root=project_root,
            data_root=data_root,
            database_path=data_root / "parallax.sqlite3",
            originals_dir=data_root / "uploads",
            derived_dir=data_root / "derived",
            reports_dir=data_root / "reports",
            web_dir=project_root / "apps" / "web",
            max_upload_bytes=max_upload_mb * 1024 * 1024,
        )

    def create_directories(self) -> None:
        for directory in (self.data_root, self.originals_dir, self.derived_dir, self.reports_dir):
            directory.mkdir(parents=True, exist_ok=True)
