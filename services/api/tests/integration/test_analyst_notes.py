from __future__ import annotations

from app.schemas.contracts import AnalystNoteCreate, CaseCreate
from app.services.cases import CaseService


def test_analyst_note_is_persisted_and_audited(case_service: CaseService) -> None:
    case = case_service.create_case(CaseCreate(reference="CYB-NOTE-01", title="Analyst note"), actor="pytest")

    note = case_service.add_analyst_note(
        case.id,
        AnalystNoteCreate(note="Request the original camera export before closing the review.", disposition="Request original source file"),
        actor="reviewer-01",
    )

    detail = case_service.get_case(case.id)
    assert detail.notes[0].id == note.id
    assert detail.notes[0].disposition == "Request original source file"
    assert "case.analyst_note.recorded" in [event.event_type for event in detail.audit_events]
    verification = case_service.verify_audit_chain(case.id)
    assert verification.chain_intact is True
