"""외부 API 클라이언트 공통 베이스."""

import re
from xml.etree.ElementTree import Element, fromstring

import httpx

_SENSITIVE_PARAM_RE = re.compile(r"(serviceKey=)[^&]+", re.IGNORECASE)


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
        self._client = httpx.Client(
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
