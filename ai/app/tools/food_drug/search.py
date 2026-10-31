"""식약 근거 조회와 의료기기 품목 조회. 조회는 "비슷한 품목 고르기"이지 판단이 아니다.

- 근거(법령 조문 + 품목·등급 별표)는 법제처에서 기준일별로 받아 캐시한다(evidence_loader).
- rank_devices: 품목·등급 별표의 품목 행을 상품 용어와의 글자 유사도로 고른다.
"""

from collections.abc import Callable, Iterable
from datetime import date, datetime

from ..common.law import KST, CachedLoader, LawApiClients
from ..common.ranking import rank_rows
from .evidence import DeviceItem, FoodDrugEvidence, load_food_drug_evidence


def rank_devices(items: Iterable[DeviceItem], terms: list[str], *, top_k: int) -> list[DeviceItem]:
    """품목명·중분류·정의와 상품 용어의 글자 2개 단위 유사도로 정렬한다. 품목명이 용어에 그대로 있으면 가산한다.

    Args:
        items: 의료기기 품목 행.
        terms: 상품 용어.
        top_k: 돌려줄 최대 행 수.

    Returns:
        list[DeviceItem]: 점수 높은 순 품목 행.
    """
    return rank_rows(
        items, terms, top_k=top_k, key=lambda item: item.item_id,
        text=lambda item: f"{item.name} {item.group} {item.definition}",
        names=lambda item: [item.name],
    )


def _load_on_demand(as_of: date) -> FoodDrugEvidence:
    """조회할 때만 법제처 조회 객체(DB 캐시 먼저, 없으면 API)를 열고 닫는다. 캐시와 함께 써서 기준일마다 한 번만 연다.

    Args:
        as_of: 기준일.

    Returns:
        FoodDrugEvidence: 기준일 근거 묶음.
    """
    from ...config import get_settings
    from ...db import open_law_fetchers

    clients = LawApiClients(*open_law_fetchers(get_settings().law_oc))
    try:
        return load_food_drug_evidence(clients, as_of)
    finally:
        clients.close()


def evidence_loader() -> Callable[[], FoodDrugEvidence]:
    """기준일(한국 날짜)의 식약 근거를 돌려주는 함수를 만든다. 법제처 응답은 DB 캐시를 먼저 봄.

    기준일별 캐시는 함수마다 따로 있어 조립하는 쪽이 한 번 만들어 공유함.

    Returns:
        Callable[[], FoodDrugEvidence]: 부를 때 오늘 기준 근거를 돌려주는 함수.
    """
    loader = CachedLoader(_load_on_demand)
    return lambda: loader.load(datetime.now(KST).date())
