from __future__ import annotations

from app.schemas.contracts import CaseCreate
from app.services.assessment import AssessmentService
from app.services.cases import CaseService


def test_assessment_service_records_an_inconclusive_case(case_service: CaseService) -> None:
    case = case_service.create_case(CaseCreate(reference="CYB-ASM-01", title="Assessment"), actor="pytest")

    assessment = AssessmentService(case_service).assess(case.id, actor="pytest")

    assert assessment.outcome == "inconclusive"
    detail = case_service.get_case(case.id)
    assert detail.assessment is not None
    assert detail.assessment.id == assessment.id
    assert "case.assessment.generated" in [event.event_type for event in detail.audit_events]
