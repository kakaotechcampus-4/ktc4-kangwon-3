"""모델 검토 실패: 원인 연결, 규칙 결과 보존, 실패 trace 한 번. 문구·사용량 공통 규칙은 base 테스트."""

import pytest
from langchain_core.messages import AIMessage

from app.agents.base import MissingParsedOutput
from app.agents.verification import VerificationAgent, VerificationError
from app.schemas.schemas import TraceEvent


def test_모델_호출_실패는_원인과_규칙_결과를_보존한다(samples, stub_model, records):
    cause = RuntimeError("rate limit exceeded")

    with pytest.raises(VerificationError) as exc_info:
        VerificationAgent(stub_model(error=cause)).run(samples.draft())

    assert exc_info.value.__cause__ is cause
    assert exc_info.value.partial_result is not None


def test_모델_호출_실패는_실패_trace를_한_번_남긴다(samples, stub_model, records):
    trace: list[TraceEvent] = []

    with pytest.raises(VerificationError):
        VerificationAgent(stub_model(error=RuntimeError("boom"))).run(samples.draft(), trace=trace)

    failed = [event for event in trace if event.action == "model_review_failed"]
    assert len(failed) == 1
    assert failed[0].detail == "_Review 생성 실패: RuntimeError"
    assert trace[-1].action == "model_review_failed"


def test_파싱_오류도_규칙_결과와_trace를_남긴다(samples, stub_model, records):
    cause = ValueError("스키마 불일치")
    model = stub_model(result={"raw": AIMessage(content=""), "parsed": None, "parsing_error": cause})
    trace: list[TraceEvent] = []

    with pytest.raises(VerificationError) as exc_info:
        VerificationAgent(model).run(samples.draft(), trace=trace)

    assert exc_info.value.__cause__ is cause
    assert exc_info.value.partial_result is not None
    assert trace[-1].detail == "_Review 생성 실패: ValueError"


def test_파싱_결과가_비면_MissingParsedOutput을_trace에_남긴다(samples, stub_model, records):
    trace: list[TraceEvent] = []

    with pytest.raises(VerificationError) as exc_info:
        VerificationAgent(stub_model()).run(samples.draft(), trace=trace)

    assert isinstance(exc_info.value.__cause__, MissingParsedOutput)
    assert trace[-1].detail == "_Review 생성 실패: MissingParsedOutput"
