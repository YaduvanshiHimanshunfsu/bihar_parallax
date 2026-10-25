from __future__ import annotations

from app.schemas.contracts import AssessmentSummary
from app.services.cases import CaseService
from forensic_engine.fusion.assessment import AssessmentSignal, assess_case


class AssessmentService:
    """Collect persisted findings and create an auditable recommendation."""

    def __init__(self, case_service: CaseService) -> None:
        self.case_service = case_service

    def assess(self, case_id: str, actor: str) -> AssessmentSummary:
        case = self.case_service.get_case(case_id)
        signals: list[AssessmentSignal] = []
        analysis_count = 0
        for item in case.evidence:
            detail = self.case_service.get_evidence_detail(item.id)
            for analysis in detail.analyses:
                analysis_count += 1
                signals.extend(
                    AssessmentSignal(
                        evidence_id=item.id,
                        module=analysis.module,
                        code=finding.code,
                        severity=finding.severity,
                        title=finding.title,
                    )
                    for finding in analysis.findings
                )
        return self.case_service.record_assessment(case_id, assess_case(signals, analysis_count), actor)
