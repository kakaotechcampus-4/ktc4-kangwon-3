"""BaseAgent 실패 처리: 호출·파싱 실패를 error_class로 감싸고 원인·부분 결과·실행 정보를 담는다 (#171 §4.2, #284)."""

import pytest
from pydantic import ValidationError

from app.agents.base import MissingParsedOutput, ModelFailurePhase


def test_호출이_실패하면_사용량_없이_기록하고_원인을_연결해_감싼다(fakes, stub_model, records):
    cause = TimeoutError("게이트웨이 응답 없음")

    with pytest.raises(fakes.Error) as caught:
        fakes.Agent(stub_model(error=cause)).run(fakes.question)

    assert caught.value.__cause__ is cause
    assert (records[0]["usage"], records[0]["ok"], records[0]["error_type"]) == (None, False, "TimeoutError")
    assert (caught.value.meta.usage, caught.value.meta.error_type) == (None, "TimeoutError")


def test_실패하면_부분_결과를_예외에_담는다(fakes, stub_model, records):
    agent = fakes.Agent(stub_model(error=TimeoutError()))

    with pytest.raises(fakes.Error) as caught:
        agent._invoke_with_meta(agent._build_messages(fakes.question), subject_id="p-1", partial_result={"rules": 1})

    assert caught.value.partial_result == {"rules": 1}


def test_파싱_오류는_사용량을_보존하고_원인을_연결해_감싼다(fakes, stub_model, records):
    cause = ValueError("스키마 불일치")
    model = stub_model(result={"raw": fakes.raw(), "parsed": None, "parsing_error": cause})

    with pytest.raises(fakes.Error) as caught:
        fakes.Agent(model).run(fakes.question)

    assert caught.value.__cause__ is cause
    assert (records[0]["ok"], records[0]["error_type"], records[0]["usage"].input_tokens) == (False, "ValueError", 100)
    assert caught.value.meta.usage.input_tokens == 100


def test_출력이_비면_MissingParsedOutput을_원인으로_연결한다(fakes, stub_model, records):
    with pytest.raises(fakes.Error) as caught:
        fakes.Agent(stub_model()).run(fakes.question)

    assert isinstance(caught.value.__cause__, MissingParsedOutput)
    assert (len(records), records[0]["error_type"]) == (1, "MissingParsedOutput")


def test_스키마와_맞지_않는_출력도_토큰을_기록하고_감싼다(fakes, stub_model, records):
    with pytest.raises(fakes.Error) as caught:
        fakes.Agent(stub_model({"wrong": 1})).run(fakes.question)

    assert isinstance(caught.value.__cause__, ValidationError)
    assert (records[0]["ok"], records[0]["error_type"], records[0]["usage"].input_tokens) == (False, "ValidationError", 100)


def test_기본_실패_문구는_호출_실패면_작업_이름_파싱_실패면_출력_이름을_쓴다(fakes, stub_model, records):
    with pytest.raises(fakes.Error, match="^가짜 작업에 실패했습니다: boom$"):
        fakes.Agent(stub_model(error=TimeoutError("boom"))).run(fakes.question)
    with pytest.raises(fakes.Error, match="^모델 응답이 Answer 스키마와 맞지 않습니다: "):
        fakes.Agent(stub_model({"wrong": 1})).run(fakes.question)
    with pytest.raises(fakes.Error, match="^모델 응답이 답변 스키마와 맞지 않습니다: "):
        fakes.Labeled(stub_model({"wrong": 1})).run(fakes.question)


def test_하위_클래스가_실패_문구를_다시_정할_수_있다(fakes, stub_model, records):
    class _Custom(fakes.Agent):
        def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
            return f"{phase.value} 실패"

    with pytest.raises(fakes.Error, match="^call 실패$"):
        _Custom(stub_model(error=TimeoutError())).run(fakes.question)
    with pytest.raises(fakes.Error, match="^parsing 실패$"):
        _Custom(stub_model({"wrong": 1})).run(fakes.question)
