from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class AssessmentSignal:
    evidence_id: str
    module: str
    code: str
    severity: str
    title: str


@dataclass(frozen=True)
class CaseAssessment:
    outcome: str
    reasons: list[str]
    signals: list[AssessmentSignal]


def assess_case(signals: Iterable[AssessmentSignal], analysis_count: int) -> CaseAssessment:
    """Recommend a review state with rules that are visible and intentionally strict.

    This does not infer legal authenticity. A high-concern recommendation requires
    multiple review-level signals from at least two distinct analysis modules.
    """
    all_signals = list(signals)
    review_signals = [signal for signal in all_signals if signal.severity == "review"]
    modules = {signal.module for signal in review_signals}
    if analysis_count == 0:
        return CaseAssessment(
            outcome="inconclusive",
            reasons=["No completed media-analysis run is recorded for this case."],
            signals=[],
        )
    if len(review_signals) >= 3 and len(modules) >= 2:
        return CaseAssessment(
            outcome="high_integrity_concern",
            reasons=[
                f"{len(review_signals)} review-level signals were recorded across {len(modules)} independent analysis modules.",
                "This is a prioritisation recommendation only; an authorised reviewer must inspect every cited signal and original file.",
            ],
            signals=review_signals,
        )
    if review_signals:
        return CaseAssessment(
            outcome="needs_expert_review",
            reasons=[
                f"{len(review_signals)} review-level signal(s) require contextual examination before any conclusion.",
                "Individual signals can arise from benign capture, export, compression, or recording conditions.",
            ],
            signals=review_signals,
        )
    return CaseAssessment(
        outcome="no_integrity_concern_detected",
        reasons=[
            "Completed analyses recorded no review-level signals under the current bounded methods.",
            "Absence of a signal does not prove that evidence is authentic, complete, or unaltered.",
        ],
        signals=[],
    )
