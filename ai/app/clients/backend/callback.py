"""콜백을 BE 수신 경로로 보내는 HTTP 전송부 (#317).

진단 이벤트: POST {BE_BASE_URL}/internal/v1/ai/products/{productId} (#305, #332).
법령 변경: POST {BE_BASE_URL}/internal/v1/ai/law-changes (#673).
헤더는 둘 다 X-Internal-Token. 응답 분류·재시도는 보내는 쪽이 맡음. 여기서는 상태 코드와 응답 본문의 code만 돌려줌.
"""

from dataclasses import dataclass
from typing import TypeVar
from urllib.parse import quote

import httpx

from ...schemas.base import ApiModel
from ...schemas.callback import LawChangeCallbackRequest, PublicProductEvent
from ..request import RequestClient
from .errors import CallbackTransportError

CALLBACK_PATH = "/internal/v1/ai/products/{product_id}"
LAW_CHANGES_PATH = "/internal/v1/ai/law-changes"
TOKEN_HEADER = "X-Internal-Token"
# 연결·응답 대기 상한. 넘으면 발신함이 재시도
TIMEOUT_SECONDS = 5.0

_RequestT = TypeVar("_RequestT")


@dataclass(frozen=True)
class SendResult:
    """BE 응답 하나.

    Attributes:
        status: HTTP 상태 코드.
        code: 응답 본문의 code (BE ApiResponse, 예: COMMON-009). 없으면 None.
    """

    status: int
    code: str | None = None


class _BackendClient(RequestClient[_RequestT, SendResult]):
    """BE 내부 API로 본문을 보내는 공통 부분. 연결은 재사용하고, 여러 전송 스레드가 같이 써도 됨.

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

    def _post_body(self, path: str, request: ApiModel) -> httpx.Response:
        """본문을 POST로 보낸다. 4xx·5xx도 예외 없이 응답을 돌려줌 (보내는 쪽이 재시도 판단).

        Args:
            path: 요청 경로.
            request: 보낼 본문.

        Returns:
            httpx.Response: BE 응답.

        Raises:
            CallbackTransportError: 타임아웃·연결 실패로 응답을 받지 못한 경우.
        """
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


class BackendCallbackClient(_BackendClient[PublicProductEvent]):
    """BE 콜백 수신부로 진단 이벤트를 보낸다."""

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
        return self._post_body(CALLBACK_PATH.format(product_id=quote(request.product_id, safe="")), request)


class BackendLawChangeClient(_BackendClient[LawChangeCallbackRequest]):
    """BE 수신부로 법령 점검이 찾은 변경 묶음을 보낸다."""

    def send(self, request: LawChangeCallbackRequest) -> SendResult:
        """변경 묶음을 보내고 BE 응답을 돌려준다.

        Args:
            request: 보낼 변경 묶음.

        Returns:
            SendResult: HTTP 상태 코드와 응답 본문의 code. 본문이 JSON이 아니거나 code가 없으면 None.

        Raises:
            CallbackTransportError: 타임아웃·연결 실패로 응답을 받지 못한 경우.
        """
        return self.fetch_parsed(request)

    def _send(self, request: LawChangeCallbackRequest) -> httpx.Response:
        """변경 묶음을 POST로 보낸다.

        Args:
            request: 보낼 변경 묶음.

        Returns:
            httpx.Response: BE 응답.

        Raises:
            CallbackTransportError: 타임아웃·연결 실패로 응답을 받지 못한 경우.
        """
        return self._post_body(LAW_CHANGES_PATH, request)


def _response_code(response: httpx.Response) -> str | None:
    """응답 본문의 code (BE ApiResponse). JSON이 아니거나 없으면 None."""
    try:
        body = response.json()
    except ValueError:
        return None
    code = body.get("code") if isinstance(body, dict) else None
    return code if isinstance(code, str) else None
