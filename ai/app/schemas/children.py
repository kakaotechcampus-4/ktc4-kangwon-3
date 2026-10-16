"""어린이제품 Tool 내부 조건 추출·품목 선택 출력. 외부 API DTO와 구분한다."""

from typing import Literal

from .base import StrictModel

ChildrenField = Literal["product_type", "target_age", "intended_use", "material", "excluded_kind"]


class ChildrenFact(StrictModel):
    """상품 인용문에서 확인한 조건 하나. 출처는 코드가 검증한다.

    excluded_kind만 값이 정해진 이름(법 제2조 제1호 단서의 제외 물품) 중 하나이고, 인용은 그 판단의 원문 근거다.
    """

    field: ChildrenField
    value: str
    evidence_id: str
    quote: str


class ChildrenFacts(StrictModel):
    facts: list[ChildrenFact]
    search_terms: list[str]


class ChildrenSelection(StrictModel):
    """후보 행 중 상품에 해당할 가능성이 있는 행 하나. 법적 적용 확정이 아니다.

    법령 인용문은 모델이 쓰지 않는다. 코드가 item_id의 행 원문을 그대로 근거로 붙인다.
    """

    item_id: str
    rationale: str
    applies: bool
    fact_fields: list[ChildrenField]
    needed_fields: list[ChildrenField]


class ChildrenReview(StrictModel):
    selections: list[ChildrenSelection]
