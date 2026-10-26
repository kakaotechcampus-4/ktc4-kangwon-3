"""통관 요건 Tool 내부 조건 추출·결정사례 선택 출력. 외부 API DTO와 구분한다."""

from typing import Literal

from .base import StrictModel

CustomsField = Literal["product_type", "material", "function", "intended_use", "composition"]


class CustomsFact(StrictModel):
    """상품 인용문에서 확인한 품목분류 결정 요소 하나. 출처는 코드가 검증한다."""

    field: CustomsField
    value: str
    evidence_id: str
    quote: str


class CustomsFacts(StrictModel):
    facts: list[CustomsFact]
    # 품목분류 결정사례를 찾을 일반 명칭. 판단 근거가 아니며 원문 대조를 하지 않는다.
    search_terms: list[str]


class CustomsSelection(StrictModel):
    """후보 결정사례 중 상품과 같은 종류의 물품으로 볼 수 있는 사례 하나. 품목분류 확정이 아니다.

    HS 코드는 모델이 쓰지 않는다. 코드가 case_id의 결정사례에 적힌 HS를 그대로 쓴다.
    """

    case_id: str
    rationale: str
    applies: bool
    fact_fields: list[CustomsField]
    needed_fields: list[CustomsField]


class CustomsReview(StrictModel):
    selections: list[CustomsSelection]
