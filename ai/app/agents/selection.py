"""선택 담당자가 구현하는 에이전트.

상품 정보(Product)를 받아 6개 심사 도메인 각각의 필요 여부를 판단한다.
툴 실행·재시도·결과 조립은 파이프라인의 책임이며 이 모듈은 선택만 돌려준다.
"""

import json

from ..schemas.agent import ToolSelectionResponse
from ..schemas.product import Product
from .base import AgentError, AgentSpec, BaseAgent


class SelectionFailedError(AgentError):
    """LLM 호출 또는 구조화 출력 파싱 실패 시 발생하는 예외.

    호출부(파이프라인)가 langchain·openai SDK의 세부 예외를 알 필요 없이
    이 하나만 잡으면 된다. 원인 예외는 ``raise ... from exc``로 보존한다.
    """


class SelectionAgent(BaseAgent[ToolSelectionResponse]):
    """상품 정보를 보고 필요한 심사 도메인을 선택한다. 툴 실행은 파이프라인의 몫이다."""

    spec = AgentSpec(
        name="selection",
        prompt="selection",
        output=ToolSelectionResponse,
        error=SelectionFailedError,
        call_failed_message="심사 도메인 선택에 실패했습니다: {exc}",
        parse_failed_message="모델 응답이 ToolSelectionResponse 스키마와 맞지 않습니다: {error}",
    )

    def select(self, product: Product) -> ToolSelectionResponse:
        """추출된 상품 정보를 받아 6개 심사 도메인의 선택 여부를 판단한다.

        Args:
            product: 추출 에이전트가 만든 Product.

        Returns:
            6개 도메인 각각의 선택 여부와 이유를 담은 ToolSelectionResponse.

        Raises:
            SelectionFailedError: LLM 호출 실패 또는 응답이 스키마와 맞지 않을 때.
        """
        return self._invoke(self._user_content(product), subject_id=product.product_id)

    @staticmethod
    def _user_content(product: Product) -> str:
        """Product를 모델에 보낼 JSON 문자열로 직렬화한다.

        Args:
            product: JSON 직렬화할 상품 정보.

        Returns:
            str: 상품 정보 JSON.
        """
        return json.dumps(product.model_dump(mode="json"), ensure_ascii=False)
