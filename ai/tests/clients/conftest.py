"""클라이언트 테스트 공통 설정. 실제 외부 API 대신 httpx.MockTransport로 응답을 돌려준다."""

from collections.abc import Callable

import httpx
import pytest

from app.clients.base import BaseClient

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def wire() -> Callable[[BaseClient, Handler], list[httpx.Request]]:
    """클라이언트의 HTTP 연결을 가짜 응답으로 바꾸고, 보낸 요청을 기록한다.

    클라이언트가 만든 base_url·공통 헤더는 그대로 두고 전송만 바꿈.

    Returns:
        Callable: (클라이언트, 응답 함수) → 보낸 요청 목록.
    """

    def _wire(client: BaseClient, handler: Handler) -> list[httpx.Request]:
        sent: list[httpx.Request] = []

        def record(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            return handler(request)

        original = client._client
        client._client = httpx.Client(
            base_url=original.base_url,
            headers=original.headers,
            transport=httpx.MockTransport(record),
        )
        original.close()
        return sent

    return _wire
