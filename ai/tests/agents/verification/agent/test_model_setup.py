"""검증 에이전트 모델 준비와 사용량: strict 구조화 출력, 모델 자동 생성 안 함, 규칙만이면 기록 안 함."""

import pytest

from app.agents.verification import VerificationAgent
from app.schemas.schemas import VerificationStatus


def test_strict_json_schema로_구조화_출력을_요구한다(samples, stub_model):
    model = stub_model(samples.review())

    VerificationAgent(model)

    # strict json_schema는 유지하고, 사용량 수집용 include_raw가 추가됨 (#171 §4.2)
    assert model.structured_calls[0][1] == {"include_raw": True, "method": "json_schema", "strict": True}


def test_모델을_주입하지_않으면_자동으로_만들지_않는다(samples, monkeypatch):
    monkeypatch.setattr("app.agents.base.agent.build_agent_model", lambda name: pytest.fail("모델을 만들면 안 됨"))

    agent = VerificationAgent()

    assert agent.verify_rules(samples.draft()).status is VerificationStatus.APPROVED


def test_사용량은_상품_ID로_검증_이름에_기록한다(samples, stub_model, records):
    VerificationAgent(stub_model(samples.review())).run(samples.draft())

    assert (len(records), records[0]["agent"], records[0]["subject_id"]) == (1, "verification", "p1")


def test_평가_실행은_운영과_다른_이름으로_집계된다(samples, stub_model, records):
    VerificationAgent(stub_model(samples.review()), usage_agent="verification-eval").run(samples.draft())

    assert records[0]["agent"] == "verification-eval"


def test_규칙_검사만_하면_사용량을_기록하지_않는다(samples, stub_model, records):
    VerificationAgent(stub_model(samples.review())).verify_rules(samples.draft())

    assert records == []
