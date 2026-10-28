"""콜백 이벤트를 BE 수신 경로로 보내는 HTTP 전송부 (#317).

POST {BE_BASE_URL}/internal/v1/ai/products/{productId}, 헤더 X-Internal-Token (#305, #332).
응답 분류·재시도는 발신함(outbox)이 맡음. 여기서는 상태 코드와 응답 본문의 code만 돌려줌.
"""

from dataclasses import dataclass
from urllib.parse import quote

import httpx

from ...schemas.callback import PublicProductEvent
from ..request import RequestClient
from .errors import CallbackTransportError

CALLBACK_PATH = "/internal/v1/ai/products/{product_id}"
TOKEN_HEADER = "X-Internal-Token"
# 연결·응답 대기 상한. 넘으면 발신함이 재시도
TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class SendResult:
    """BE 응답 하나.

    Attributes:
        status: HTTP 상태 코드.
        code: 응답 본문의 code (BE ApiResponse, 예: COMMON-009). 없으면 None.
    """

    status: int
    code: str | None = None


class BackendCallbackClient(RequestClient[PublicProductEvent, SendResult]):
    """BE 콜백 수신부로 이벤트를 보낸다. 연결은 재사용하고, 여러 전송 스레드가 같이 써도 됨.

    Args:
        base_url: BE 주소 (BE_BASE_URL).
        token: BE 내부 API 토큰 (INTERNAL_API_TOKEN).
        timeout: 요청 하나의 대기 상한(초).
        transport: httpx 전송 계층. 테스트에서 가짜 BE를 붙일 때 주입.
    """

    API = "backend"

    def __init__(
        self, base_url: str, token: str, *, timeout: float = TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url.rstrip("/"), timeout=timeout, headers={TOKEN_HEADER: token}, transport=transport,
        )

    def send(self, event: PublicProductEvent) -> SendResult:
        """이벤트 하나를 보내고 BE 응답을 돌려준다. 발신함(CallbackSender)이 부르는 입구.

        Args:
            event: 보낼 콜백 이벤트.

        Returns:
            SendResult: HTTP 상태 코드와 응답 본문의 code. 본문이 JSON이 아니거나 code가 없으면 None.

        Raises:
            CallbackTransportError: 타임아웃·연결 실패로 응답을 받지 못한 경우.
        """
        return self.fetch_parsed(event)

    def _send(self, request: PublicProductEvent) -> httpx.Response:
        """이벤트를 POST로 보낸다. 4xx·5xx도 예외 없이 응답을 돌려줌 (발신함이 재시도 판단).

        Args:
            request: 보낼 콜백 이벤트.

        Returns:
            httpx.Response: BE 응답.

        Raises:
            CallbackTransportError: 타임아웃·연결 실패로 응답을 받지 못한 경우.
        """
        path = CALLBACK_PATH.format(product_id=quote(request.product_id, safe=""))
        # 기본값으로 채워지는 eventType이 빠지지 않게 exclude_unset·exclude_defaults 쓰지 않음 (BE #329)
        body = request.model_dump(mode="json", by_alias=True)
        try:
            # _post는 4xx·5xx에서 예외를 내므로 직접 보냄
            return self._client.post(path, json=body)
        except httpx.TransportError as exc:
            raise CallbackTransportError(f"콜백 전송 실패: {type(exc).__name__}: {exc}") from exc

    def _parse(self, raw: httpx.Response) -> SendResult:
        """BE 응답을 상태 코드와 응답 본문의 code로 바꾼다.

        Args:
            raw: BE 응답.

        Returns:
            SendResult: 전송 결과.
        """
        return SendResult(raw.status_code, _response_code(raw))


def _response_code(response: httpx.Response) -> str | None:
    """응답 본문의 code (BE ApiResponse). JSON이 아니거나 없으면 None."""
    try:
        body = response.json()
    except ValueError:
        return None
    code = body.get("code") if isinstance(body, dict) else None
    return code if isinstance(code, str) else None
