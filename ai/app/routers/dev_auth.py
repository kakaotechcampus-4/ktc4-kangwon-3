"""샌드박스 진단 엔드포인트(/api/ai/v1/sandbox/**)의 켜기·API 키 검사.

라우터는 항상 등록하고 요청마다 검사함. 꺼져 있으면 경로가 없는 것처럼 404, 키가 없거나 틀리면 401.
키는 응답·로그에 남기지 않고, 비교는 길이·내용과 관계없이 같은 시간이 걸리게 함.
"""

import hmac

from fastapi import Depends
from fastapi.security import APIKeyHeader

from ..config import Settings, get_settings
from ..domain.errors import AIResponseCode, AIServiceError

DEV_API_KEY_HEADER = "X-Dev-Api-Key"

# Swagger의 Authorize 버튼으로 키를 넣을 수 있게 보안 방식으로 등록. 검사는 아래 함수가 직접 함
_dev_api_key = APIKeyHeader(name=DEV_API_KEY_HEADER, auto_error=False, description="개발용 진단 API 키")


def require_dev_api_key(
    key: str | None = Depends(_dev_api_key),
    settings: Settings = Depends(get_settings),
) -> None:
    """개발용 진단이 켜져 있고 키가 맞을 때만 통과시킨다.

    Args:
        key: X-Dev-Api-Key 헤더 값.
        settings: 서버 설정.

    Raises:
        AIServiceError: 꺼져 있으면 404(AI_NOT_FOUND), 키가 없거나 틀리면 401(AI_UNAUTHORIZED).
    """
    if not settings.dev_api_enabled:
        raise AIServiceError(response_code=AIResponseCode.NOT_FOUND.value)
    if key is None or not hmac.compare_digest(key.encode("utf-8"), settings.dev_api_key.encode("utf-8")):
        raise AIServiceError(response_code=AIResponseCode.UNAUTHORIZED.value)
