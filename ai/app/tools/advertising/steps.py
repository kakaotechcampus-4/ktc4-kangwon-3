"""표시·광고 Tool의 모델 호출 단계: 판매자 문구 검토."""

import json
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from ...agents.base import BaseAgent, ModelFailurePhase
from ...prompts import PromptName
from ...schemas.advertising import AdvertisingReview
from ...schemas.product import Product
from ...schemas.schemas import ToolName
from .errors import AdvertisingReviewError


@dataclass(frozen=True)
class AdvertisingReviewInput:
    """문구 검토 입력.

    Attributes:
        product: 사용량 기록과 문맥(상품 이름·종류)에 쓸 상품.
        lines: 검토할 판매자 문구. 빈 줄은 뺀 listing_text.
    """

    product: Product
    lines: list[str]


class AdvertisingReviewer(BaseAgent[AdvertisingReviewInput, AdvertisingReview, AdvertisingReview]):
    """listing_text에서 실증이 필요한 주장을 인용하는 모델 호출부."""

    component_name = "advertising"
    # Tool 안에서 쓰는 에이전트라 TOOL_PROFILES의 표시·광고 Tool 프로필로 모델을 고름
    model_profile = ("tool", ToolName.LABEL_AD)
    prompt_name = PromptName.ADVERTISING
    output_schema = AdvertisingReview
    error_class = AdvertisingReviewError

    def _build_messages(self, input: AdvertisingReviewInput) -> list[SystemMessage | HumanMessage]:
        """상품 이름·종류와 판매자 문구로 모델 메시지를 만든다.

        Args:
            input: 문구 검토 입력.

        Returns:
            list[SystemMessage | HumanMessage]: 모델에 보낼 메시지.
        """
        product = input.product
        payload = {"product_name": product.product_name, "category": product.category, "listing_text": input.lines}
        return self._messages(json.dumps(payload, ensure_ascii=False))

    def _subject_id(self, input: AdvertisingReviewInput) -> str:
        """사용량 기록 대상 ID.

        Args:
            input: 문구 검토 입력.

        Returns:
            str: 상품 ID.
        """
        return input.product.product_id

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """실패 문구를 만든다. 원인은 예외 이름만 넣음.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        # 응답을 못 받은 실패
        if phase is ModelFailurePhase.CALL:
            return f"표시·광고 문구 검토 모델 호출에 실패했습니다: {type(cause).__name__}"
        return f"모델 응답이 AdvertisingReview 스키마와 맞지 않습니다: {type(cause).__name__}"
