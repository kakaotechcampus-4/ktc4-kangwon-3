"""상품 정보로 6개 심사 도메인의 선택 여부를 판단하는 에이전트. 툴 실행·재시도·결과 조립은 파이프라인 몫."""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from ...prompts import PromptName, get_prompt
from ...schemas.agent import ToolSelectionResponse
from ...schemas.product import Product
from ...schemas.schemas import ToolName
from ..base import BaseAgent
from .errors import SelectionFailedError

# 평가 러너 호환용. 러너가 공용 로더로 옮겨가면 제거 (#171 §3.2)
PROMPT_PATH = get_prompt(PromptName.SELECTION).path

# 모델 판단과 상관없이 항상 실행하는 Tool (#588). 실상품 평가에서 모델이 표시광고를 고른 회차가 18%뿐이었고,
# 표시광고는 결과 상태 계산에서 빠져 있어(results/status.py) 오경고가 진단 결론을 바꾸지 않는다.
ALWAYS_RUN_TOOLS = frozenset({ToolName.LABEL_AD})
ALWAYS_RUN_REASON = "판매 문구의 표시·광고 표현은 모든 상품에서 확인합니다."


class SelectionAgent(BaseAgent[Product, ToolSelectionResponse, ToolSelectionResponse]):
    """추출된 상품 정보를 보고 6개 심사 도메인 각각의 선택 여부와 이유를 낸다.

    평가 호출은 usage_agent("selection-eval")로 운영 비용과 구분.
    """

    component_name = "selection"
    prompt_name = PromptName.SELECTION
    output_schema = ToolSelectionResponse
    error_class = SelectionFailedError
    task_name = "심사 도메인 선택"

    def _subject_id(self, input: Product) -> str:
        """사용량 기록 대상 ID.

        Args:
            input: 추출된 상품 정보.

        Returns:
            str: 상품 ID.
        """
        return input.product_id

    def _build_messages(self, input: Product) -> list[SystemMessage | HumanMessage]:
        """상품 정보 JSON으로 모델 메시지를 만든다.

        Args:
            input: 추출된 상품 정보.

        Returns:
            list[SystemMessage | HumanMessage]: [시스템 프롬프트, 상품 JSON].
        """
        return self._messages(json.dumps(input.model_dump(mode="json"), ensure_ascii=False))

    def _finalize(self, output: ToolSelectionResponse, input: Product) -> ToolSelectionResponse:
        """항상 실행하는 Tool을 선택으로 고정한다. 모델이 이미 골랐으면 모델의 이유를 남긴다.

        Args:
            output: 모델이 낸 6개 Tool 판단.
            input: 추출된 상품 정보.

        Returns:
            ToolSelectionResponse: 항상 실행 Tool이 선택된 판단.
        """
        decisions = [
            decision if decision.selected or decision.tool_name not in ALWAYS_RUN_TOOLS
            else decision.model_copy(update={"selected": True, "reason": ALWAYS_RUN_REASON})
            for decision in output.decisions
        ]
        return output.model_copy(update={"decisions": decisions})
