"""선택 담당자가 구현하는 에이전트.

상품 정보(Product)를 받아 6개 심사 도메인 각각의 필요 여부를 판단한다.
툴 실행·재시도·결과 조립은 파이프라인의 책임이며 이 모듈은 선택만 돌려준다.
"""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from ..prompts import PromptName, get_prompt
from ..schemas.agent import ToolSelectionResponse
from ..schemas.product import Product
from .base import AgentError, BaseAgent, MissingParsedOutput, ModelFailurePhase

# 평가 러너 호환용. 러너가 공용 로더로 옮겨가면 제거 (#171 §3.2)
_PROMPT_PATH = get_prompt(PromptName.SELECTION).path


class SelectionFailedError(AgentError):
    """LLM 호출 또는 구조화 출력 파싱 실패 시 발생하는 예외.

    호출부(파이프라인)가 langchain·openai SDK의 세부 예외를 알 필요 없이
    이 하나만 잡으면 된다. 원인 예외는 ``raise ... from exc``로 보존한다.
    """


class SelectionAgent(BaseAgent[ToolSelectionResponse]):
    """상품 정보를 보고 필요한 심사 도메인을 선택한다. 툴 실행은 파이프라인의 몫이다.

    생성자는 BaseAgent 그대로. 모델 미주입 시 build_chat_model()로 생성하고,
    평가 호출은 usage_agent("selection-eval" 등)로 운영 비용과 나눠 집계함.
    """

    component_name = "selection"
    prompt_name = PromptName.SELECTION
    output_schema = ToolSelectionResponse
    error_class = SelectionFailedError

    def select(self, product: Product) -> ToolSelectionResponse:
        """추출된 상품 정보를 받아 6개 심사 도메인의 선택 여부를 판단한다.

        Args:
            product: 추출 에이전트가 만든 Product.

        Returns:
            6개 도메인 각각의 선택 여부와 이유를 담은 ToolSelectionResponse.

        Raises:
            SelectionFailedError: LLM 호출 실패 또는 응답이 스키마와 맞지 않을 때.
        """
        # 시스템 프롬프트와 Product JSON을 LLM 메시지 리스트로 조립한다.
        messages = self._build_messages(product)

        # 호출·파싱 실패 기록과 SelectionFailedError 변환, 사용량·콘솔 로그는 BaseAgent가 맡음
        return self._invoke(messages, subject_id=product.product_id)

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """기존 선택 실패 문구를 돌려준다. parsed 누락은 기존처럼 원인 자리에 None 표기.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        if phase is ModelFailurePhase.CALL:
            return f"심사 도메인 선택에 실패했습니다: {cause}"
        detail = None if isinstance(cause, MissingParsedOutput) else cause
        return f"모델 응답이 ToolSelectionResponse 스키마와 맞지 않습니다: {detail}"

    def _build_messages(self, product: Product) -> list[SystemMessage | HumanMessage]:
        """시스템 프롬프트와 Product JSON을 LLM 메시지 리스트로 조립한다.

        Args:
            product: JSON 직렬화할 상품 정보.

        Returns:
            [SystemMessage(프롬프트), HumanMessage(상품 JSON)] 리스트.
        """
        # 추출 에이전트에게 받은 데이터를 JSON으로 직렬화한다.
        payload = product.model_dump(mode="json")

        return self._messages(json.dumps(payload, ensure_ascii=False))
