"""식약 근거 조회와 의료기기 품목 조회. 조회는 "비슷한 품목 고르기"이지 판단이 아니다.

- 근거(법령 조문 + 품목·등급 별표)는 법제처에서 기준일별로 받아 캐시한다(default_evidence_loader).
- rank_devices: 품목·등급 별표의 품목 행을 상품 용어와의 글자 유사도로 고른다.
  DB의 medical_devices 테이블은 개별 제품의 허가 정보(품목명·분류번호·등급)다. 적재되면 "같은 분류번호로
  허가된 제품이 있는지" 보조 근거로 쓸 수 있지만, 품목 분류 자체는 이 별표가 기준이다.
"""

import threading
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta, timezone

from ..common.law import CachedLoader, LawApiClients
from ..common.ranking import rank_rows
from .evidence import DeviceItem, FoodDrugEvidence, load_food_drug_evidence

KST = timezone(timedelta(hours=9))


def rank_devices(items: Iterable[DeviceItem], terms: list[str], *, top_k: int) -> list[DeviceItem]:
    """품목명·중분류·정의와 상품 용어의 글자 2개 단위 유사도로 정렬한다. 품목명이 용어에 그대로 있으면 가산한다."""
    return rank_rows(
        items, terms, top_k=top_k, key=lambda item: item.item_id,
        text=lambda item: f"{item.name} {item.group} {item.definition}",
        names=lambda item: [item.name],
    )


def _load_on_demand(as_of: date) -> FoodDrugEvidence:
    """조회할 때만 법제처 클라이언트를 열고 닫는다. 캐시와 함께 써서 기준일마다 한 번만 연다."""
    from ...config import get_settings

    clients = LawApiClients.from_oc(get_settings().law_oc)
    try:
        return load_food_drug_evidence(clients, as_of)
    finally:
        clients.close()


_default_lock = threading.Lock()
_default_loader: CachedLoader | None = None


def default_evidence_loader() -> Callable[[], FoodDrugEvidence]:
    """기준일(한국 날짜)의 식약 근거를 돌려주는 함수. 프로세스 공용 캐시를 쓴다."""
    global _default_loader
    with _default_lock:
        if _default_loader is None:
            _default_loader = CachedLoader(_load_on_demand)
        loader = _default_loader
    return lambda: loader.load(datetime.now(KST).date())
