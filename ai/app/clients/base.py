"""외부 API 클라이언트 공통 베이스."""

import re
import time
from xml.etree.ElementTree import Element, fromstring

import httpx

from ..metrics import EXTERNAL_API_DURATION, EXTERNAL_API_REQUESTS

_SENSITIVE_PARAM_RE = re.compile(r"(serviceKey=)[^&]+", re.IGNORECASE)


class _InstrumentedClient(httpx.Client):
    """모든 요청의 결과와 소요시간을 지표로 남기는 httpx 클라이언트.

    send()는 응답 본문을 다 읽은 뒤 반환하므로 본문 수신 시간까지 포함된다.
    _get/_post를 거치지 않고 self._client를 직접 쓰는 호출도 함께 집계된다.

    Args:
        client_name: 지표 라벨로 쓸 클라이언트 이름.
        **kwargs: httpx.Client 생성 인자.
    """

    def __init__(self, client_name: str, **kwargs):
        super().__init__(**kwargs)
        self._client_name = client_name

    def send(self, request: httpx.Request, **kwargs) -> httpx.Response:
        """요청을 보내고 결과(success, http_error, timeout, connection_error)를 기록한다.

        Args:
            request: 보낼 요청.
            **kwargs: httpx.Client.send 인자.

        Returns:
            httpx.Response: 응답.
        """
        start = time.perf_counter()
        result = "connection_error"
        try:
            response = super().send(request, **kwargs)
            result = "success" if response.is_success else "http_error"
            return response
        except httpx.TimeoutException:
            result = "timeout"
            raise
        finally:
            EXTERNAL_API_REQUESTS.labels(client=self._client_name, result=result).inc()
            EXTERNAL_API_DURATION.labels(client=self._client_name).observe(time.perf_counter() - start)


class BaseClient:
    """외부 공공 API 호출에 필요한 공통 기능을 제공하는 베이스 클라이언트.

    Args:
        base_url: API 도메인 주소. 서브클래스에서 지정한다.
        timeout: 요청 제한 시간(초). 기본 10초.
        headers: 모든 요청에 포함할 공통 헤더.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        headers: dict[str, str] | None = None,
    ):
        self._client = _InstrumentedClient(
            type(self).__name__,
            base_url=base_url,
            timeout=timeout,
            headers=headers or {},
        )

    # -- 요청 --

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        """GET 요청을 보내고 응답을 반환한다.

        Args:
            path: base_url 뒤에 붙는 요청 경로.
            params: 쿼리 파라미터.

        Returns:
            httpx.Response: HTTP 응답 객체.

        Raises:
            httpx.HTTPStatusError: 4xx/5xx 응답 시.
        """
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response

    def _post(self, path: str, json: dict | None = None) -> httpx.Response:
        """POST 요청을 보내고 응답을 반환한다.

        Args:
            path: base_url 뒤에 붙는 요청 경로.
            json: JSON 요청 본문.

        Returns:
            httpx.Response: HTTP 응답 객체.

        Raises:
            httpx.HTTPStatusError: 4xx/5xx 응답 시.
        """
        response = self._client.post(path, json=json)
        response.raise_for_status()
        return response

    @staticmethod
    def _mask_url(error: httpx.HTTPStatusError) -> httpx.HTTPStatusError:
        """HTTPStatusError 메시지에서 민감한 쿼리 파라미터를 마스킹한다.

        Args:
            error: 원본 예외.

        Returns:
            httpx.HTTPStatusError: URL이 마스킹된 새 예외.
        """
        masked_msg = _SENSITIVE_PARAM_RE.sub(r"\1***", str(error))
        return httpx.HTTPStatusError(
            message=masked_msg,
            request=error.request,
            response=error.response,
        )

    # -- 응답 파싱 --

    def _parse_json(self, response: httpx.Response) -> dict:
        """응답 본문을 JSON으로 파싱한다.

        Args:
            response: HTTP 응답 객체.

        Returns:
            dict: 파싱된 JSON 데이터.
        """
        return response.json()

    def _parse_xml(self, response: httpx.Response) -> Element:
        """응답 본문을 XML Element로 파싱한다.

        Args:
            response: HTTP 응답 객체.

        Returns:
            Element: 파싱된 XML 루트 엘리먼트.
        """
        return fromstring(response.text)

    # -- 정리 --

    def close(self) -> None:
        """HTTP 클라이언트 연결을 정리한다."""
        self._client.close()
