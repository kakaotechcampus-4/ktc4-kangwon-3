"""모델 검토 범위 검사: 모든 판단을 한 번씩, 없는 ID 참조 금지. 실패해도 규칙 결과·실행 정보 보존."""

import pytest

from app.agents.verification import VerificationAgent, VerificationError
from app.agents.verification.schemas import _Issue
from app.schemas.schemas import TraceEvent


def test_검토_범위가_다르면_실패_trace와_규칙_결과를_남긴다(samples, stub_model, records):
    agent = VerificationAgent(stub_model(samples.review(checked_finding_ids=[])))
    trace: list[TraceEvent] = []

    with pytest.raises(VerificationError, match="검토 범위") as exc_info:
        agent.run(samples.draft(), trace=trace)

    assert trace[-1].action == "review_validation_failed"
    assert trace[-1].status == "failed"
    assert exc_info.value.partial_result is not None
    assert exc_info.value.partial_result.checked_finding_ids == []
    # 모델은 이미 불렀으므로 실행 정보도 담김
    assert exc_info.value.meta is not None


def test_검토_범위에_중복이_있으면_실패한다(samples, stub_model, records):
    agent = VerificationAgent(stub_model(samples.review(checked_finding_ids=["f1", "f1"])))

    with pytest.raises(VerificationError, match="중복"):
        agent.run(samples.draft())


def test_존재하지_않는_판단_ID를_참조하면_실패한다(samples, stub_model, records):
    review = samples.review(
        issues=[
            _Issue(
                severity="warning",
                issue_type="contradiction",
                description="없는 판단을 가리킨다.",
                related_finding_ids=["없는-id"],
                recommended_action=None,
            )
        ]
    )
    agent = VerificationAgent(stub_model(review))

    with pytest.raises(VerificationError, match="존재하지 않는"):
        agent.run(samples.draft())
