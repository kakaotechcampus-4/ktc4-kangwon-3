"""더미 진단 엔드포인트(/api/ai/v1/dummy/diagnose/**)의 내부 토큰 검사.

AI→BE 콜백과 같은 토큰(INTERNAL_API_TOKEN)을 BE→AI 요청에도 씀. 토큰이 없거나 틀리면 401.
Swagger는 공개라 요청 형식은 보이지만, 토큰 없이는 더미로 BE에 콜백을 보낼 수 없음.
토큰은 응답·로그에 남기지 않고, 비교는 길이·내용과 관계없이 같은 시간이 걸리게 함.
"""

import hmac

from fastapi import Depends, status
from fastapi.security import APIKeyHeader

from ..config import Settings, get_settings
from ..domain.errors import AIResponseCode, AIServiceError
from ..schemas.response import ApiResponse

INTERNAL_TOKEN_HEADER = "X-Internal-Token"

# Swagger의 Authorize 버튼으로 토큰을 넣을 수 있게 보안 방식으로 등록. 검사는 아래 함수가 직접 함
# 이름을 따로 줘야 개발용 키와 Swagger 보안 방식이 겹치지 않음 (기본 이름은 둘 다 APIKeyHeader)
_internal_token = APIKeyHeader(name=INTERNAL_TOKEN_HEADER, scheme_name="InternalToken", auto_error=False,
                               description="BE 내부 API 토큰")

INTERNAL_AUTH_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"model": ApiResponse, "description": "내부 토큰이 없거나 틀림"},
}


def require_internal_token(
    token: str | None = Depends(_internal_token),
    settings: Settings = Depends(get_settings),
) -> None:
    """내부 토큰이 맞을 때만 통과시킨다.

    Args:
        token: X-Internal-Token 헤더 값.
        settings: 서버 설정.

    Raises:
        AIServiceError: 토큰이 없거나 틀리면 401(AI_UNAUTHORIZED).
    """
    if token is None or not hmac.compare_digest(token.encode("utf-8"), settings.internal_api_token.encode("utf-8")):
        raise AIServiceError(response_code=AIResponseCode.UNAUTHORIZED.value)
