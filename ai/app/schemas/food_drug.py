"""식약 Tool 내부 조건 추출·의료기기 품목 선택 출력. 외부 API DTO와 구분한다."""

from typing import Literal

from .base import StrictModel

FoodDrugField = Literal[
    "product_type", "material", "intended_use", "food_contact", "edible", "skin_applied",
    "health_claim", "beauty_claim", "ingredient",
]


class FoodDrugFact(StrictModel):
    """상품 인용문에서 확인한 조건 하나. 출처는 코드가 검증한다.

    food_contact·edible·skin_applied는 값이 판단 결과("예"/"아니오")이고 인용은 그 판단의 원문 근거다.
    - food_contact: 음식·음료에 직접 닿는 쓰임인지(식품용 기구·용기)
    - edible: 사람이 먹거나 마시는 것인지(식품·건강기능식품)
    - skin_applied: 피부·모발·손발톱 등에 바르거나 문지르거나 뿌려 쓰는 것인지(화장품)
    health_claim은 질병·상해의 진단·치료·경감·예방이나 신체 구조·기능의 검사·측정·개선을 말하는 원문 표현,
    beauty_claim은 미백·주름·자외선 차단·모발 색·탈모·여드름 등 피부·모발에 대한 효과를 말하는 원문 표현,
    ingredient는 원문에 적힌 성분·원료 이름 하나다.
    """

    field: FoodDrugField
    value: str
    evidence_id: str
    quote: str


class Judgment(StrictModel):
    """해당 여부 판단 하나. "모름"이 아니면 quote가 그 판단의 원문 근거다(코드가 대조한다)."""

    answer: Literal["예", "아니오", "모름"]
    evidence_id: str
    quote: str


class Judgments(StrictModel):
    """모델이 매번 반드시 답하는 세 판단. 선택 칸으로 두면 모델이 건너뛰는 일이 잦았다(실측)."""

    food_contact: Judgment
    edible: Judgment
    skin_applied: Judgment


class FoodDrugFacts(StrictModel):
    facts: list[FoodDrugFact]
    judgments: Judgments
    # 의료기기 품목표에서 비슷한 품목을 찾을 일반 명칭. 그런 기구가 아니면 비운다. 판단 근거가 아니다.
    device_terms: list[str]
    # beauty_claim이 화장품법 시행규칙 제2조 기능성화장품 범위의 몇 호에 해당하는지(입력 functional_types의 number).
    functional_types: list[int]


class DeviceSelection(StrictModel):
    """후보 품목 중 상품에 해당할 가능성이 있는 의료기기 품목 하나. 의료기기 해당 확정이 아니다.

    법령 인용문과 등급은 모델이 쓰지 않는다. 코드가 item_id의 품목 행을 그대로 근거로 붙인다.
    """

    item_id: str
    rationale: str
    applies: bool
    fact_fields: list[FoodDrugField]
    needed_fields: list[FoodDrugField]


class DeviceReview(StrictModel):
    selections: list[DeviceSelection]
