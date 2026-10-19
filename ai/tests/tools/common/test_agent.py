"""ToolStep 계약: 규제 Tool(전기·어린이)과 전기 평가 러너가 기대는 겉모양.

- ``ToolStep[출력]`` 하위 클래스 + ``failure_label``
- ``run(ToolStepInput(payload, subject_id))`` → 검증된 출력
- 실패 문구에 "모델 호출"/"구조화 출력", 원인은 ``__cause__``에만
- 인스턴스에서 ``step.run``을 덮어썼다가 ``del``로 되돌림 (electrical 평가 러너)
"""

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.prompts import PromptName
from app.tools.common.agent import ToolModelError, ToolStep, ToolStepInput


_EMPTY = ToolStepInput({}, "p-1")


class _Facts(BaseModel):
    value: str


class _FactsError(ToolModelError):
    pass


class _FactsStep(ToolStep[_Facts]):
    component_name = "facts-step"
    prompt_name = PromptName.CHILDREN_FACTS
    output_schema = _Facts
    error_class = _FactsError
    failure_label = "가짜 Tool 조건 추출"


class _Model:
    """정해 둔 본문을 돌려주거나 예외를 던지는 모델."""

    def __init__(self, content: str = "", error: Exception | None = None) -> None:
        self._content = content
        self._error = error
        self.received: list[list[Any]] = []

    def with_structured_output(self, schema: Any, **kwargs: Any) -> "_Model":
        return self

    def invoke(self, messages: list[Any]) -> dict[str, Any]:
        self.received.append(messages)
        if self._error is not None:
            raise self._error
        usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        return {"raw": AIMessage(content=self._content, usage_metadata=usage), "parsed": None, "parsing_error": None}


@pytest.fixture
def records(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "app.usage.record",
        lambda agent, usage, **kwargs: captured.append({"agent": agent, "usage": usage, **kwargs}),
    )
    return captured


def test_payload를_JSON으로_보내고_검증된_출력을_돌려준다(records):
    model = _Model('{"value": "ok"}')

    result = _FactsStep(model).run(ToolStepInput({"hints": ["전지"], "이름": "선풍기"}, "p-1"))

    assert result == _Facts(value="ok")
    assert json.loads(model.received[0][-1].content) == {"hints": ["전지"], "이름": "선풍기"}
    assert (records[0]["agent"], records[0]["subject_id"]) == ("facts-step", "p-1")


def test_호출_실패는_모델_호출_문구로_감싸고_원인은_체인에만_둔다(records):
    cause = TimeoutError("게이트웨이 비밀 응답")

    with pytest.raises(_FactsError) as caught:
        _FactsStep(_Model(error=cause)).run(_EMPTY)

    assert "모델 호출" in str(caught.value)
    assert "가짜 Tool 조건 추출" in str(caught.value)
    assert "게이트웨이 비밀 응답" not in str(caught.value)
    assert caught.value.__cause__ is cause


def test_출력이_스키마와_다르면_구조화_출력_문구로_감싼다(records):
    with pytest.raises(_FactsError) as caught:
        _FactsStep(_Model('{"wrong": 1}')).run(_EMPTY)

    assert "구조화 출력" in str(caught.value)
    assert caught.value.__cause__ is not None


def test_Tool_오류는_ToolModelError_계열로_잡힌다(records):
    # Tool은 ToolModelError로 받아 실패 결과를 만듦
    with pytest.raises(ToolModelError):
        _FactsStep(_Model(error=RuntimeError())).run(_EMPTY)


def test_인스턴스에서_run을_덮어썼다가_지우면_원래_run으로_돌아온다(records):
    step = _FactsStep(_Model('{"value": "ok"}'))

    step.run = lambda input: _Facts(value="가짜")
    assert step.run(_EMPTY).value == "가짜"
    del step.run

    assert step.run(_EMPTY).value == "ok"
