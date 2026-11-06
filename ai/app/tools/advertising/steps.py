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
        product: 사용량 기록에 쓸 상품.
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
        """판매자 문구로 모델 메시지를 만든다.

        상품 이름·종류는 비워서 보냄. 추출한 상품 이름이 판매자 제목 줄과 같아서, 채우면 모델이 제목 줄의 효능 구절을
        "상품 이름"으로 보고 뺌('굽은 등 교정기', #349). 평가 실행기와 같은 입력이라 평가 결과가 그대로 서비스 결과가 됨.
        칸 자체를 없애면 평가셋 고정 입력 맞힘이 떨어짐(실측은 #483).

        Args:
            input: 문구 검토 입력.

        Returns:
            list[SystemMessage | HumanMessage]: 모델에 보낼 메시지.
        """
        payload = {"product_name": None, "category": None, "listing_text": input.lines}
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
