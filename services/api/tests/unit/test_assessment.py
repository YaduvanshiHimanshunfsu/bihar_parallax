from __future__ import annotations

from forensic_engine.fusion.assessment import AssessmentSignal, assess_case


def signal(module: str, code: str = "review.signal") -> AssessmentSignal:
    return AssessmentSignal(evidence_id="evidence-1", module=module, code=code, severity="review", title="Review signal")


def test_assessment_is_inconclusive_without_completed_analysis() -> None:
    result = assess_case([], analysis_count=0)
    assert result.outcome == "inconclusive"


def test_single_review_signal_requires_expert_review() -> None:
    result = assess_case([signal("image.metadata_ela")], analysis_count=1)
    assert result.outcome == "needs_expert_review"


def test_high_concern_requires_multiple_independent_modules() -> None:
    result = assess_case(
        [signal("image.metadata_ela", "image.one"), signal("video.frame_sequence", "video.one"), signal("video.frame_sequence", "video.two")],
        analysis_count=2,
    )
    assert result.outcome == "high_integrity_concern"
    assert len(result.signals) == 3
