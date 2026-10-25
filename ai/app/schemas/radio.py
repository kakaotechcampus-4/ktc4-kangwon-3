"""전파 Tool 내부 조건 추출·품목 선택 출력. 외부 API DTO와 구분한다."""

from typing import Literal

from .base import StrictModel

RadioField = Literal["product_type", "wireless_feature", "frequency", "output_power", "intended_use"]


class RadioFact(StrictModel):
    """상품 인용문에서 확인한 조건 하나. 출처는 코드가 검증한다."""

    field: RadioField
    value: str
    evidence_id: str
    quote: str


class RadioFacts(StrictModel):
    facts: list[RadioFact]
    search_terms: list[str]


class RadioSelection(StrictModel):
    """후보 행 중 상품에 해당할 가능성이 있는 행 하나. 법적 적용 확정이 아니다.

    적합성평가 유형과 법령 인용문은 모델이 쓰지 않는다. 코드가 item_id의 행 값과 원문을 붙인다.
    """

    item_id: str
    rationale: str
    applies: bool
    fact_fields: list[RadioField]
    needed_fields: list[RadioField]


class RadioReview(StrictModel):
    selections: list[RadioSelection]
