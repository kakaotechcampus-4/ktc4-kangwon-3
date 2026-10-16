"""판매 사이트 상품 페이지 클라이언트 공통 베이스."""

from collections.abc import Callable, Iterable
from typing import ClassVar, TypeVar

import httpx
from bs4 import BeautifulSoup

from ..base import BaseClient
from ...schemas.clients.marketplace_request import ProductPageRequest
from ...schemas.clients.marketplace_response import ProductPage

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)

T = TypeVar("T")


class MarketplaceBaseClient(BaseClient[ProductPageRequest, ProductPage]):
    """판매 사이트 상품 페이지 클라이언트 공통 베이스.

    방식 : GET/HTML
    서비스 키 : 불필요. 단, 브라우저 헤더 필수.
    비고
        판매자마다 하위 도메인이 달라 base_url 없이 상품 주소 전체로 요청.
        하위 클라이언트는 `SITE`·`_parse`만 구현. 형식 변환만 하고 이미지 고르기는 쓰는 쪽.
    """

    SITE: ClassVar[str]

    def __init__(self):
        super().__init__(
            base_url="",
            timeout=15.0,
            # 헤더 없으면 아마존은 차단 페이지(3.7KB)를 돌려줌 (#322)
            headers={"User-Agent": _BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"},
        )

    def _send(self, request: ProductPageRequest) -> httpx.Response:
        """상품 페이지 HTML을 받는다.

        Args:
            request: 상품 페이지 조회 요청.

        Returns:
            httpx.Response: HTML 원문 응답.

        Raises:
            httpx.HTTPStatusError: 4xx/5xx 응답인 경우.
        """
        response = self._client.get(request.url, follow_redirects=True)
        response.raise_for_status()
        return response

    @staticmethod
    def _soup(response: httpx.Response) -> BeautifulSoup:
        """응답 HTML을 bs4 문서로 읽는다. 추가 의존성 없이 표준 html.parser 사용."""
        return BeautifulSoup(response.text, "html.parser")

    @staticmethod
    def _unique(items: Iterable[T], key: Callable[[T], str]) -> list[T]:
        """같은 키(같은 사진 등)는 처음 것만 남긴다. 순서 유지.

        Args:
            items: 항목 목록.
            key: 같은 항목을 가리는 키.

        Returns:
            list[T]: 중복을 뺀 목록.
        """
        seen: set[str] = set()
        unique = []
        for item in items:
            if (value := key(item)) not in seen:
                seen.add(value)
                unique.append(item)
        return unique
