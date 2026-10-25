from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.db.database import Database
from app.evidence.storage import EvidenceStore
from app.services.cases import CaseService


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    data_root = tmp_path / "data"
    active_settings = Settings(
        project_root=tmp_path,
        data_root=data_root,
        database_path=data_root / "parallax.sqlite3",
        originals_dir=data_root / "uploads",
        derived_dir=data_root / "derived",
        reports_dir=data_root / "reports",
        web_dir=tmp_path / "web",
        max_upload_bytes=1024 * 1024,
    )
    active_settings.create_directories()
    Database(active_settings.database_path).initialise()
    return active_settings


@pytest.fixture()
def case_service(settings: Settings) -> CaseService:
    return CaseService(Database(settings.database_path))


@pytest.fixture()
def evidence_store(settings: Settings) -> EvidenceStore:
    return EvidenceStore(settings.originals_dir, settings.max_upload_bytes)
