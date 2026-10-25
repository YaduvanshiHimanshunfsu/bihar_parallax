from __future__ import annotations

import json
import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class Database:
    """Small explicit SQLite repository for the local hackathon MVP.

    Original evidence lives in object-style storage on disk; only a relative
    storage key and forensic metadata are stored in SQLite.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialise(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    reference TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence_items (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
                    original_filename TEXT NOT NULL,
                    storage_key TEXT NOT NULL UNIQUE,
                    media_type TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    original_immutable INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT REFERENCES cases(id) ON DELETE SET NULL,
                    evidence_id TEXT REFERENCES evidence_items(id) ON DELETE SET NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    previous_event_hash TEXT,
                    event_hash TEXT
                );

                CREATE TABLE IF NOT EXISTS derived_artifacts (
                    id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL REFERENCES evidence_items(id) ON DELETE RESTRICT,
                    artifact_type TEXT NOT NULL,
                    storage_key TEXT NOT NULL UNIQUE,
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL REFERENCES evidence_items(id) ON DELETE RESTRICT,
                    module TEXT NOT NULL,
                    module_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS findings (
                    id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
                    code TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis_artifacts (
                    analysis_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
                    artifact_id TEXT NOT NULL REFERENCES derived_artifacts(id) ON DELETE RESTRICT,
                    PRIMARY KEY (analysis_id, artifact_id)
                );

                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
                    report_format TEXT NOT NULL,
                    storage_key TEXT NOT NULL UNIQUE,
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS case_assessments (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE RESTRICT,
                    outcome TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    signals_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_case_id ON evidence_items(case_id);
                CREATE INDEX IF NOT EXISTS idx_audit_case_id ON audit_events(case_id);
                CREATE INDEX IF NOT EXISTS idx_audit_evidence_id ON audit_events(evidence_id);
                CREATE INDEX IF NOT EXISTS idx_analysis_evidence_id ON analysis_runs(evidence_id);
                CREATE INDEX IF NOT EXISTS idx_findings_analysis_id ON findings(analysis_id);
                CREATE INDEX IF NOT EXISTS idx_reports_case_id ON reports(case_id);
                CREATE INDEX IF NOT EXISTS idx_assessments_case_id ON case_assessments(case_id, created_at DESC);
                """
            )
            # SQLite's CREATE TABLE IF NOT EXISTS does not evolve existing local
            # demo databases. These additive migrations preserve previous events
            # as legacy/unsealed records rather than rewriting their history.
            audit_columns = {row["name"] for row in connection.execute("PRAGMA table_info(audit_events)")}
            if "previous_event_hash" not in audit_columns:
                connection.execute("ALTER TABLE audit_events ADD COLUMN previous_event_hash TEXT")
            if "event_hash" not in audit_columns:
                connection.execute("ALTER TABLE audit_events ADD COLUMN event_hash TEXT")

    @staticmethod
    def audit_event_hash(
        *,
        case_id: str | None,
        evidence_id: str | None,
        event_type: str,
        actor: str,
        details: dict[str, Any],
        created_at: str,
        previous_event_hash: str | None,
    ) -> str:
        """Hash the canonical event payload, chained to the previous case event.

        This detects accidental or unauthorised changes inside the local database.
        A production deployment should additionally anchor chain heads outside the
        database or sign them using a managed key.
        """
        payload = {
            "actor": actor,
            "case_id": case_id,
            "created_at": created_at,
            "details": details,
            "evidence_id": evidence_id,
            "event_type": event_type,
            "previous_event_hash": previous_event_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def add_audit_event(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        actor: str,
        details: dict[str, Any],
        case_id: str | None = None,
        evidence_id: str | None = None,
    ) -> None:
        created_at = utc_now()
        previous_event_hash: str | None = None
        if case_id is not None:
            previous = connection.execute(
                """
                SELECT event_hash FROM audit_events
                WHERE case_id = ? AND event_hash IS NOT NULL
                ORDER BY id DESC LIMIT 1
                """,
                (case_id,),
            ).fetchone()
            previous_event_hash = previous["event_hash"] if previous else None
        event_hash = self.audit_event_hash(
            case_id=case_id,
            evidence_id=evidence_id,
            event_type=event_type,
            actor=actor,
            details=details,
            created_at=created_at,
            previous_event_hash=previous_event_hash,
        )
        connection.execute(
            """
            INSERT INTO audit_events(
                case_id, evidence_id, event_type, actor, details_json, created_at, previous_event_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id, evidence_id, event_type, actor, json.dumps(details, sort_keys=True), created_at,
                previous_event_hash, event_hash,
            ),
        )
