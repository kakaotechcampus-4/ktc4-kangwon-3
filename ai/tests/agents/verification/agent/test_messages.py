"""모델에 보내는 초안: 조회 파라미터·원시 응답·오류·Tool 안 findings 제외, 프롬프트에 스키마 없음."""

import contextlib
import json

import pytest

from app.agents.verification import VerificationAgent, VerificationError
from app.agents.verification.schemas import _Review


def test_조회_파라미터와_원시_응답은_모델에_보내지_않는다(samples, stub_model, records):
    draft = samples.draft()
    draft.tool_results[-1].query = {"api_key": "절대-보내면-안-됨"}
    draft.tool_results[-1].raw_response = {"body": "원시 응답"}
    draft.tool_results[-1].error = "내부 오류 메시지"
    original = draft.model_dump(mode="json")
    model = stub_model(samples.review())

    VerificationAgent(model).run(draft)

    payload = model.received[0][-1]["content"]
    assert "절대-보내면-안-됨" not in payload
    assert "원시 응답" not in payload
    assert "내부 오류 메시지" not in payload
    # 모델 전송용 복사본만 정리하고 파이프라인이 보관하는 초안은 변경하지 않는다.
    assert draft.model_dump(mode="json") == original


def test_툴_판단은_최상위_findings로만_모델에_보낸다(samples, stub_model, records):
    model = stub_model(samples.review())

    VerificationAgent(model).run(samples.draft())

    payload = json.loads(model.received[0][-1]["content"])["draft"]
    assert [f["finding_id"] for f in payload["findings"]] == ["f1"]
    assert all("findings" not in record for record in payload["tool_results"])


def test_출력_스키마를_프롬프트에_중복으로_붙이지_않는다(samples, stub_model, records):
    # with_structured_output이 스키마를 API에 직접 전달하므로 프롬프트에는 넣지 않는다.
    model = stub_model(samples.review())

    VerificationAgent(model).run(samples.draft())

    system_prompt = model.received[0][0]["content"]
    assert "checked_finding_ids" in system_prompt  # 규칙 설명은 있다
    assert "앞 단계의 도메인 판단을 반복하지 않는다" in system_prompt
    assert "다시 `missing_evidence`로 지적하지 않는다" in system_prompt
    assert "$defs" not in system_prompt  # JSON Schema 본문은 없다


def test_요청_본문은_검토_스키마를_strict로_넘길_때와_같다(samples, fake_gateway, records):
    draft = samples.draft()
    actual: list[dict] = []
    agent = VerificationAgent(fake_gateway("{}", "stop", actual))
    expected: list[dict] = []
    reference = fake_gateway("{}", "stop", expected).with_structured_output(
        _Review, method="json_schema", strict=True,
    )

    # 응답 "{}"는 스키마와 맞지 않아 양쪽 모두 실패하지만 요청 본문은 이미 기록됨
    with contextlib.suppress(Exception):
        reference.invoke(agent._build_messages(draft))
    with pytest.raises(VerificationError):
        agent.run(draft)

    assert actual == expected
