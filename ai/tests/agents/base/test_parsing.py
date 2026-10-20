"""모델 응답 → 출력 스키마 검증(parse_structured_output). 본문은 엄격한 JSON, 본문이 없을 때만 parsed·parsing_error를 본다."""

import pytest
from langchain_core.messages import AIMessage
from langchain_openai.chat_models.base import OpenAIRefusalError
from pydantic import BaseModel, ValidationError

from app.agents.base import MissingParsedOutput
from app.agents.base.parsing import parse_structured_output


class _Answer(BaseModel):
    value: str


def _parse(content: str = "", *, parsed=None, parsing_error=None, refusal: str | None = None) -> _Answer:
    raw = AIMessage(content=content, additional_kwargs={"refusal": refusal} if refusal else {})
    return parse_structured_output({"raw": raw, "parsed": parsed, "parsing_error": parsing_error}, _Answer, "fake")


def test_본문이_있으면_엄격한_JSON으로_검증한다():
    assert _parse('{"value": "ok"}') == _Answer(value="ok")
    with pytest.raises(ValidationError):
        _parse('```json\n{"value": "ok"}\n```')


def test_본문이_있으면_LangChain이_보정한_parsed는_쓰지_않는다():
    with pytest.raises(ValidationError):
        _parse('{"value": "ok"', parsed=_Answer(value="ok"))


def test_모델이_거절하면_OpenAIRefusalError를_낸다():
    with pytest.raises(OpenAIRefusalError, match="처리할 수 없습니다"):
        _parse(refusal="처리할 수 없습니다.")


def test_본문이_없으면_parsed를_출력_스키마로_검증한다():
    assert _parse(parsed={"value": "ok"}) == _Answer(value="ok")
    with pytest.raises(ValidationError):
        _parse(parsed={"wrong": 1})


def test_본문_없이_온_파싱_오류는_예외면_그대로_문자열이면_MissingParsedOutput으로_낸다():
    cause = ValueError("스키마 불일치")
    with pytest.raises(ValueError) as caught:
        _parse(parsing_error=cause)
    assert caught.value is cause

    with pytest.raises(MissingParsedOutput, match="파싱 실패"):
        _parse(parsing_error="잘못된 JSON")


def test_본문도_parsed도_없으면_MissingParsedOutput을_낸다():
    with pytest.raises(MissingParsedOutput, match="비어 있습니다"):
        _parse("   ")
