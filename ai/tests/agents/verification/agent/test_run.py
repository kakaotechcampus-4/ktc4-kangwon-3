"""VerificationAgent 실행 흐름: 규칙 → 모델 검토 → 병합, trace 단계, 모델 없이 run."""

import pytest

from app.agents.verification import VerificationAgent, VerificationError
from app.schemas.schemas import TraceEvent, VerificationStatus


def test_문제가_없으면_approved를_돌려준다(samples, stub_model, records):
    result = VerificationAgent(stub_model(samples.review())).run(samples.draft())

    assert result.status is VerificationStatus.APPROVED
    assert result.checked_finding_ids == ["f1"]


def test_trace에_DraftAssessment부터_VerificationResult까지_변환을_남긴다(samples, stub_model, records):
    trace: list[TraceEvent] = []

    result = VerificationAgent(stub_model(samples.review())).run(samples.draft(), trace=trace)

    assert result.status is VerificationStatus.APPROVED
    assert [event.sequence for event in trace] == list(range(1, len(trace) + 1))
    assert [event.action for event in trace] == [
        "verification_started",
        "rules_started",
        "rules_completed",
        "model_review_started",
        "model_review_completed",
        "scope_validated",
        "result_merged",
        "verification_completed",
    ]
    assert "DraftAssessment" in trace[0].detail
    assert "_Review" in trace[4].detail
    assert "VerificationResult" in trace[-1].detail


def test_모델_없이_run을_부르면_규칙_결과를_보존하고_실패한다(samples):
    with pytest.raises(VerificationError) as exc_info:
        VerificationAgent().run(samples.draft())

    assert exc_info.value.partial_result is not None
    assert exc_info.value.partial_result.review_summary.startswith("규칙 검사만")
