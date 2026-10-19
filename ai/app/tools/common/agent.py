"""규제 Tool 안의 모델 호출 한 단계(조건 추출, 품목 선택). 공통 실행 인터페이스(Agent)로 호출·사용량 기록·예외 변환을 맞춤."""

import json
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from ...agents.base import Agent, AgentError, ModelFailurePhase

_Output = TypeVar("_Output", bound=BaseModel)


class ToolModelError(AgentError):
    """규제 Tool의 모델 호출·구조화 출력 실패. 원인은 예외 체인에 보존한다."""


@dataclass(frozen=True)
class ToolStepInput:
    """단계 입력. 모델에 JSON으로 보낼 값과 사용량 기록 대상 ID.

    Attributes:
        payload: 모델에 보낼 값.
        subject_id: 사용량 기록 대상 ID (상품 ID).
    """

    payload: dict[str, Any]
    subject_id: str


class ToolStep(Agent[ToolStepInput, _Output, _Output]):
    """입력 dict를 JSON으로 보내고 구조화 출력을 받는 단계.

    하위 클래스는 component_name, prompt_name, output_schema, error_class와 failure_label을 정함.
    모델은 Tool이 한 번 만들어 두 단계에 같이 넘김 (model=None이면 설정으로 만듦).
    ``run(payload, subject_id=)`` 모양은 열린 Tool PR(radio·electrical·customs·food_drug) 머지 전까지 유지.
    """

    failure_label: str = "규제 Tool"

    def run(self, payload: dict[str, Any], *, subject_id: str) -> _Output:  # type: ignore[override]
        """payload를 모델에 보내 구조화 출력을 받는다.

        Args:
            payload: 모델에 JSON으로 보낼 값.
            subject_id: 사용량 기록 대상 ID (상품 ID).

        Returns:
            _Output: 검증된 구조화 출력.

        Raises:
            AgentError: 모델 호출·파싱 실패. 실제 타입은 ``error_class``.
        """
        return self.run_with_meta(ToolStepInput(payload, subject_id)).result

    def _build_messages(self, input: ToolStepInput) -> list[SystemMessage | HumanMessage]:
        """payload를 JSON 문자열로 바꿔 모델 메시지를 만든다.

        Args:
            input: 단계 입력.

        Returns:
            list[SystemMessage | HumanMessage]: 모델에 보낼 메시지.
        """
        return self._messages(json.dumps(input.payload, ensure_ascii=False))

    def _subject_id(self, input: ToolStepInput) -> str:
        """사용량 기록 대상 ID.

        Args:
            input: 단계 입력.

        Returns:
            str: 상품 ID.
        """
        return input.subject_id

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """실패 문구를 만든다. 원인 예외 내용은 넣지 않음 (예외 체인에만 보존).

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        # 응답은 받았으나 구조화 출력이 안 맞음
        if phase is ModelFailurePhase.PARSING:
            return f"{self.failure_label} 구조화 출력을 읽을 수 없습니다."
        return f"{self.failure_label} 모델 호출에 실패했습니다."
