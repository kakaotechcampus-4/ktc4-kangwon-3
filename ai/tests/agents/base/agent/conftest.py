"""BaseAgent 테스트용 가짜 에이전트. 테스트 파일끼리 import하지 않으므로 ``fakes`` fixture로 공유한다."""

from dataclasses import dataclass
from enum import StrEnum
from types import SimpleNamespace
from typing import Literal

import pytest
from langchain_core.messages import AIMessage
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import AgentError, BaseAgent
from app.prompts import PromptName


@dataclass(frozen=True)
class Question:
    product_id: str
    text: str


class Answer(BaseModel):
    value: str


class FakeError(AgentError):
    pass


class FakeAgent(BaseAgent[Question, Answer, str]):
    """입력 글을 그대로 보내고 출력 value를 대문자로 바꿔 돌려주는 에이전트."""

    component_name = "fake"
    prompt_name = PromptName.EXTRACTION
    output_schema = Answer
    error_class = FakeError
    task_name = "가짜 작업"

    def _build_messages(self, input: Question) -> list:
        return self._messages(input.text)

    def _subject_id(self, input: Question) -> str:
        return input.product_id

    def _finalize(self, output: Answer, input: Question) -> str:
        return output.value.upper()


class LabeledAgent(FakeAgent):
    output_label = "답변"


class StrictAgent(FakeAgent):
    structured_output_options = {"method": "json_schema", "strict": True}


class RulesOnlyAgent(FakeAgent):
    creates_default_model = False


class SkippingAgent(FakeAgent):
    """빈 글이면 모델 없이 결과를 정한다."""

    def _skip(self, input: Question) -> str | None:
        return "건너뜀" if not input.text else None


class Kind(StrEnum):
    A = "a"
    B = "b"


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    kind: Kind
    level: Literal["low", "high"]
    note: str | None


class Rich(BaseModel):
    """실제 출력 스키마의 특징(중첩 모델·enum·Literal·Optional·리스트·제약)을 갖춘 가짜 스키마."""

    model_config = ConfigDict(extra="forbid")

    items: list[Item]
    flag: bool | None = None


class RichAgent(FakeAgent):
    output_schema = Rich


class StrictRichAgent(RichAgent):
    structured_output_options = {"method": "json_schema", "strict": True}


def raw_with_usage(input_tokens: int = 100, cached: int = 40, output: int = 20) -> AIMessage:
    """본문 없이 사용량만 있는 원본 응답 (parsed·parsing_error를 직접 주는 특수 응답용)."""
    return AIMessage(
        content="",
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output,
            "total_tokens": input_tokens + output,
            "input_token_details": {"cache_read": cached},
        },
    )


@pytest.fixture
def fakes() -> SimpleNamespace:
    """가짜 에이전트·스키마·입력 묶음.

    ``fakes.Agent``(기본), ``Labeled``·``Strict``·``RulesOnly``·``Skipping``·``Rich``·``StrictRich``,
    ``fakes.Answer``·``Question``·``Error``, 기본 입력 ``fakes.question``, SDK 변환 스키마 ``fakes.answer_format``,
    원본 응답 ``fakes.raw()``.
    """
    return SimpleNamespace(
        Agent=FakeAgent,
        Labeled=LabeledAgent,
        Strict=StrictAgent,
        RulesOnly=RulesOnlyAgent,
        Skipping=SkippingAgent,
        Rich=RichAgent,
        StrictRich=StrictRichAgent,
        Answer=Answer,
        Question=Question,
        Error=FakeError,
        question=Question(product_id="p-1", text="질문"),
        # SDK가 Pydantic 클래스를 변환할 때와 같은 dict 스키마의 json_schema 부분
        answer_format=type_to_response_format_param(Answer)["json_schema"],
        raw=raw_with_usage,
    )
