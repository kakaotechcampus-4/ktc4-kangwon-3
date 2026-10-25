"""관세청 세관장확인대상물품 GW 조회용 DB 우선 조회 객체.

HS 코드는 상품마다 달라 미리 받아 둘 수 없으므로 조회할 때 쌓고 하루 보관한다.
"""

from collections.abc import Callable
from datetime import timedelta

from sqlalchemy.orm import Session

from ..clients.customs import CustomsGwClient
from ..config import CUSTOMS_GW_TTL_SECONDS
from ..schemas.clients.customs_response import CustomsGwConfirmationResponse
from .engine import get_session_factory
from .errors import DatabaseNotConfiguredError
from .fetchers import OnDemandFetcher


def build_customs_gw_fetcher(service_key: str, session_factory: Callable[[], Session] | None,
                             ) -> OnDemandFetcher[CustomsGwConfirmationResponse]:
    """세관장확인대상물품 GW의 DB 우선 조회 객체를 만든다.

    Args:
        service_key: 공공데이터포털 서비스 키.
        session_factory: DB 세션을 만드는 함수. None이면 캐시 없이 클라이언트만 쓴다.

    Returns:
        OnDemandFetcher[CustomsGwConfirmationResponse]: 보관 시간 CUSTOMS_GW_TTL_SECONDS.
    """
    return OnDemandFetcher(
        CustomsGwClient(service_key), name="customs.gw", response_type=CustomsGwConfirmationResponse,
        ttl=timedelta(seconds=CUSTOMS_GW_TTL_SECONDS), session_factory=session_factory)


def open_customs_gw_fetcher(service_key: str) -> OnDemandFetcher[CustomsGwConfirmationResponse]:
    """Tool이 쓰는 세관장확인대상물품 GW 조회 객체를 공용 DB에 연결해 만든다. 다 쓰면 close()로 닫는다.

    Args:
        service_key: 공공데이터포털 서비스 키.

    Returns:
        OnDemandFetcher[CustomsGwConfirmationResponse]: DATABASE_URL이 없으면 캐시 없이 클라이언트만 쓰는 조회 객체.

    Raises:
        ConfigError: DB 엔진을 만들 수 없는 경우.
    """
    try:
        session_factory = get_session_factory()
    except DatabaseNotConfiguredError:
        session_factory = None
    return build_customs_gw_fetcher(service_key, session_factory)
