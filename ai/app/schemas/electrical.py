"""전기 Tool 내부 조건 추출·품목 선택 출력. 외부 API DTO와 구분한다."""

from typing import Literal

from pydantic import Field

from .base import StrictModel

ElectricalField = Literal[
    "product_type", "power_source", "rated_voltage", "intended_use",
    "battery_only", "adapter_included", "rated_power",
]


class ElectricalFact(StrictModel):
    """상품 인용문에서 확인한 조건 하나. 출처는 코드가 검증한다."""

    field: ElectricalField
    value: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class ElectricalFacts(StrictModel):
    facts: list[ElectricalFact] = Field(default_factory=list)
    # 품목표 조회용 일반 명칭. 판단 근거가 아니며 원문 대조를 하지 않는다.
    search_terms: list[str] = Field(default_factory=list, max_length=3)


class ElectricalSelection(StrictModel):
    """후보 행 중 상품에 해당할 가능성이 있는 행 하나. 법적 적용 확정이 아니다.

    법령 인용문은 모델이 쓰지 않는다. 코드가 item_id의 행 원문을 그대로 근거로 붙인다.
    """

    item_id: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    fact_fields: list[ElectricalField] = Field(min_length=1)
    needed_fields: list[ElectricalField] = Field(default_factory=list)


class ElectricalReview(StrictModel):
    selections: list[ElectricalSelection] = Field(default_factory=list, max_length=3)
