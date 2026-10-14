"""규제 Tool 안의 모델 호출 한 단계(조건 추출, 품목 선택). 공통 BaseAgent(#284)로 호출·사용량 기록·예외 변환을 맞춘다."""

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from ...agents.base import AgentError, BaseAgent, ModelFailurePhase

_Output = TypeVar("_Output", bound=BaseModel)


class ToolModelError(AgentError):
    """규제 Tool의 모델 호출·구조화 출력 실패. 원인은 예외 체인에 보존한다."""


class ToolStep(BaseAgent[_Output]):
    """입력 dict를 JSON으로 보내고 구조화 출력을 받는 단계.

    하위 클래스는 component_name, prompt_name, output_schema, error_class와 failure_label을 정한다.
    모델은 Tool이 한 번 만들어 두 단계에 같이 넘긴다(model=None이면 BaseAgent가 설정으로 만든다).
    """

    failure_label: str = "규제 Tool"

    def run(self, payload: dict[str, Any], *, subject_id: str) -> _Output:
        return self._invoke(self._messages(json.dumps(payload, ensure_ascii=False)), subject_id=subject_id)

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        if phase is ModelFailurePhase.PARSING:
            return f"{self.failure_label} 구조화 출력을 읽을 수 없습니다."
        return f"{self.failure_label} 모델 호출에 실패했습니다."
