"""규칙·모델 결과 병합: 같은 지적은 한 번(issue_id 제외 5개 필드), 겹치는 질문은 required가 강한 쪽."""

from app.agents.verification import VerificationAgent
from app.agents.verification.schemas import _Issue
from app.schemas.product import Product
from app.schemas.schemas import (
    FollowUpQuestion,
    ToolName,
    VerificationIssueType,
    VerificationStatus,
)


def test_규칙과_모델의_동일한_지적은_한_번만_남긴다(samples, stub_model, records):
    description = (
        "radio_compliance: 상품에 검토 신호가 있으나 툴이 선택되지 않았습니다. "
        "적용 여부를 추가 검토하세요."
    )
    recommended_action = "관련 입력과 툴 결과를 보완한 뒤 다시 검증하세요."

    review = samples.review(
        issues=[
            _Issue(
                severity="warning",
                issue_type="missing_tool",
                description=description,
                related_finding_ids=[],
                recommended_action=recommended_action,
            )
        ]
    )

    # 규칙 검사에서도 동일한 radio_compliance 누락 이슈가 생성된다.
    draft = samples.draft(Product(product_id="p1", wireless_comm=True))

    result = VerificationAgent(stub_model(review)).run(draft)

    assert len(result.issues) == 1
    assert result.issues[0].issue_type is VerificationIssueType.MISSING_TOOL
    assert result.issues[0].description == description


def test_같은_유형이어도_내용이_다른_지적은_모두_남긴다(samples, stub_model, records):
    review = samples.review(
        issues=[
            _Issue(
                severity="warning",
                issue_type="missing_evidence",
                description="법령 인용문이 부족합니다.",
                related_finding_ids=["f1"],
                recommended_action="인용문을 추가하세요.",
            ),
            _Issue(
                severity="warning",
                issue_type="missing_evidence",
                description="출처 URL이 부족합니다.",
                related_finding_ids=["f1"],
                recommended_action="출처 URL을 추가하세요.",
            ),
        ]
    )

    result = VerificationAgent(stub_model(review)).run(samples.draft())

    assert len(result.issues) == 2
    assert {issue.description for issue in result.issues} == {
        "법령 인용문이 부족합니다.",
        "출처 URL이 부족합니다.",
    }


def test_겹치는_질문은_required가_강한_쪽을_남긴다(samples, stub_model, records):
    draft = samples.draft()
    existing = FollowUpQuestion(
        question="전지 용량(Wh)이 표기되어 있습니까?",
        reason="초안 단계에서 확인하지 못했습니다.",
        related_tools=[ToolName.ELECTRICAL],
        required=False,
    )
    draft.follow_up_questions = [existing]
    review = samples.review(follow_up_questions=[samples.battery_question()])

    result = VerificationAgent(stub_model(review)).run(draft)

    assert len(result.follow_up_questions) == 1
    merged = result.follow_up_questions[0]
    assert merged.required is True
    assert merged.question_id == existing.question_id  # 기존 식별자 보존
    assert result.status is VerificationStatus.USER_INPUT_REQUIRED
