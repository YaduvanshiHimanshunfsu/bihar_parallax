from __future__ import annotations

import sqlite3

from app.db.database import Database
from app.schemas.contracts import CaseCreate
from app.services.cases import CaseService


def test_new_case_audit_events_form_a_verifiable_chain(case_service: CaseService) -> None:
    case = case_service.create_case(CaseCreate(reference="CYB-CHAIN-01", title="Audit chain"), actor="pytest")

    verification = case_service.verify_audit_chain(case.id)

    assert verification.chain_intact is True
    assert verification.total_events == 1
    assert verification.sealed_events == 1
    assert verification.legacy_unsealed_events == 0
    event = case_service.get_case(case.id).audit_events[0]
    assert event.event_hash is not None
    assert event.previous_event_hash is None


def test_audit_chain_detects_changed_event_data(case_service: CaseService) -> None:
    case = case_service.create_case(CaseCreate(reference="CYB-CHAIN-02", title="Tamper check"), actor="pytest")
    with case_service.database.connection() as connection:
        connection.execute(
            "UPDATE audit_events SET details_json = ? WHERE case_id = ?",
            ('{"reference":"CHANGED"}', case.id),
        )

    verification = case_service.verify_audit_chain(case.id)

    assert verification.chain_intact is False
    assert verification.invalid_event_id is not None
    assert "does not match" in verification.verification_note


def test_database_migration_adds_chain_columns_without_rewriting_legacy_rows(tmp_path) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT,
                evidence_id TEXT,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO audit_events(case_id, evidence_id, event_type, actor, details_json, created_at)
            VALUES ('legacy-case', NULL, 'case.created', 'legacy', '{}', '2026-01-01T00:00:00+00:00')
            """
        )

    Database(database_path).initialise()

    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(audit_events)")}
        legacy = connection.execute("SELECT previous_event_hash, event_hash FROM audit_events WHERE id = 1").fetchone()
    assert {"previous_event_hash", "event_hash"} <= columns
    assert legacy == (None, None)
