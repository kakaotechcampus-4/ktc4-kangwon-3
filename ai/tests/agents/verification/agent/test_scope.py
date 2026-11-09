"""모델 검토 범위 검사: 모든 판단 검토, 없는 ID 참조 금지. 실패해도 규칙 결과·실행 정보 보존."""

import pytest
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import ValidationError

from app.agents.verification import VerificationAgent, VerificationError
from app.agents.verification.agent import review_schema
from app.agents.verification.schemas import _Issue, _Review
from app.schemas.schemas import TraceEvent


def _two_findings(samples):
    draft = samples.draft()
    draft.findings.append(draft.findings[0].model_copy(update={"finding_id": "f2"}))
    return draft


def test_검토_범위가_다르면_실패_trace와_규칙_결과를_남긴다(samples, stub_model, records):
    # 스키마는 개수·값만 고정해 같은 ID를 두 번 쓰고 하나를 빠뜨리는 출력은 범위 검사가 잡음 (#742)
    agent = VerificationAgent(stub_model(samples.review(checked_finding_ids=["f1", "f1"])))
    trace: list[TraceEvent] = []

    with pytest.raises(VerificationError, match="검토 범위") as exc_info:
        agent.run(_two_findings(samples), trace=trace)

    assert trace[-1].action == "review_validation_failed"
    assert trace[-1].status == "failed"
    assert exc_info.value.partial_result is not None
    assert exc_info.value.partial_result.checked_finding_ids == []
    # 모델은 이미 불렀으므로 실행 정보도 담기고, 사용량은 finalize 실패 1행
    assert exc_info.value.meta is not None
    assert [(row["ok"], row["failure_phase"]) for row in records] == [(False, "finalize")]


@pytest.mark.parametrize("checked", [[], ["f1", "f1"], ["f9"]], ids=["빠뜨림", "반복", "없는_ID"])
def test_검토_범위가_초안의_판단_ID_목록을_벗어나면_파싱_실패다(samples, stub_model, records, checked):
    # 출력 스키마가 초안의 판단 ID와 개수로 좁혀져, 실제 모델은 이런 출력을 내지 못함 (#720·#742)
    agent = VerificationAgent(stub_model(samples.review(checked_finding_ids=checked)))

    with pytest.raises(VerificationError) as exc_info:
        agent.run(samples.draft())

    assert exc_info.value.partial_result is not None
    assert [(row["ok"], row["failure_phase"]) for row in records] == [(False, "parsing")]


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


def test_출력_스키마는_검토_판단_ID의_값과_개수를_초안의_판단_ID로_고정한다():
    schema = type_to_response_format_param(review_schema(["f1", "f2", "f1"]))["json_schema"]

    checked = schema["schema"]["properties"]["checked_finding_ids"]
    # 초안에 같은 ID가 두 번 있어도 한 번만
    assert (checked["items"]["enum"], checked["minItems"], checked["maxItems"]) == (["f1", "f2"], 2, 2)
    # 요청 스키마 이름과 나머지 필드는 그대로
    assert schema["name"] == "_Review"
    assert set(schema["schema"]["properties"]) == set(_Review.model_fields)


def test_판단이_없는_초안은_빈_검토_목록만_받는다():
    schema = review_schema([])

    assert schema.model_validate(
        {"issues": [], "additional_tools_required": [], "follow_up_questions": [], "checked_finding_ids": []},
    ).checked_finding_ids == []
    with pytest.raises(ValidationError):
        schema.model_validate(
            {"issues": [], "additional_tools_required": [], "follow_up_questions": [], "checked_finding_ids": ["f1"]},
        )
