"""표시·광고 근거 조회. 근거 조문은 법제처에서 기준일별로 받아 캐시한다(evidence_loader)."""

from collections.abc import Callable
from datetime import date, datetime

from ..common.law import KST, CachedLoader, LawApiClients
from .evidence import AdvertisingEvidence, load_advertising_evidence


def _load_on_demand(as_of: date) -> AdvertisingEvidence:
    """조회할 때만 법제처 조회 객체(DB 캐시 먼저, 없으면 API)를 열고 닫는다. 캐시와 함께 써서 기준일마다 한 번만 연다.

    Args:
        as_of: 기준일.

    Returns:
        AdvertisingEvidence: 기준일 근거 묶음.
    """
    from ...config import get_settings
    from ...db import open_law_fetchers

    clients = LawApiClients(*open_law_fetchers(get_settings().law_oc))
    try:
        return load_advertising_evidence(clients, as_of)
    finally:
        clients.close()


def evidence_loader() -> Callable[[], AdvertisingEvidence]:
    """기준일(한국 날짜)의 표시·광고 근거를 돌려주는 함수를 만든다. 법제처 응답은 DB 캐시를 먼저 봄.

    기준일별 캐시는 함수마다 따로 있어 조립하는 쪽이 한 번 만들어 공유함.

    Returns:
        Callable[[], AdvertisingEvidence]: 부를 때 오늘 기준 근거를 돌려주는 함수.
    """
    loader = CachedLoader(_load_on_demand)
    return lambda: loader.load(datetime.now(KST).date())
