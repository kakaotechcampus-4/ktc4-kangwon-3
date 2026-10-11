"""국립전파연구원 적합성평가 클라이언트 공통 베이스."""

from typing import ClassVar
from xml.etree.ElementTree import Element

import httpx

from ..base import BaseClient, ResponseT
from ...schemas.clients.radio_request import RadioAuthRequest

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)


class RadioBaseClient(BaseClient[RadioAuthRequest, ResponseT]):
    """국립전파연구원(emsit) 적합성평가 클라이언트 공통 베이스.

    방식 : GET/XML
    서비스 키 : 불필요. 단, 브라우저 User-Agent 헤더 필수.
    비고
        인증정보 조회(getAuthInfo)와 유효여부 조회(getAuthStatus)가 같은 요청 형식을 씀.
        하위 클라이언트는 `_ENDPOINT`와 `_parse`만 구현.
        없는 번호도 HTTP 200이며 resultCode로 판별해야 함.
    """

    _ENDPOINT: ClassVar[str]

    def __init__(self):
        super().__init__(
            base_url="http://emsit.go.kr/openapi/service/AuthenticationInfoService",
            headers={"User-Agent": _BROWSER_UA},
        )

    def _send(self, request: RadioAuthRequest) -> httpx.Response:
        """인증번호로 조회를 요청한다.

        Args:
            request: 인증번호 조회 요청.

        Returns:
            httpx.Response: XML 원문 응답.

        Raises:
            httpx.HTTPStatusError: API 응답이 4xx/5xx인 경우.
        """
        return self._get(self._ENDPOINT, params={
            "mtlCefNo": request.mtl_cef_no,             # 적합성평가 인증번호
        })

    @staticmethod
    def _text(element: Element, tag: str) -> str | None:
        """XML 엘리먼트에서 태그의 텍스트를 꺼낸다.

        Args:
            element: 부모 엘리먼트.
            tag: 찾을 태그명.

        Returns:
            str | None: 태그 텍스트. 없으면 None.
        """
        child = element.find(tag)
        if child is not None and child.text and child.text.strip():
            return child.text.strip()
        return None
