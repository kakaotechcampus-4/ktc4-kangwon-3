"""판매 사이트 상품 페이지 클라이언트 공통 베이스.

안전 규칙은 하위 클라이언트가 빠뜨리지 않게 베이스에서 강제함.
    - 요청: 처음 주소와 리다이렉트마다 사이트 도메인(DOMAINS) 안인지 확인, 리다이렉트 횟수·응답 크기 상한
    - 이미지: 사이트 이미지 서버(IMAGE_DOMAINS)의 https 주소만. 페이지가 정한 아무 주소를 모델에 넘기지 않음
    - 판매자 글: 보이지 않는 문자(폭 0·글자 방향 바꾸기·제어 문자) 제거, 줄 수·줄 길이·전체 길이 상한
      판매자 글은 그대로 모델 입력이 되어, 숨긴 지시문·거대한 주입 문구·비용 폭탄을 줄임
"""

import re
from collections.abc import Callable, Iterable
from typing import ClassVar, TypeVar

import httpx
from bs4 import BeautifulSoup

from ..base import BaseClient
from ...schemas.clients.marketplace_request import ProductPageRequest
from ...schemas.clients.marketplace_response import ProductPage, ProductPageImage

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)

# 리다이렉트를 따라가는 최대 횟수
MAX_REDIRECTS = 5
# 상품 페이지 응답 크기 상한. Made-in-China 상세 페이지 약 260KB, 아마존 약 2.2MB (#322)
MAX_PAGE_BYTES = 5 * 1024 * 1024
# 판매자 글 상한. Made-in-China 상품 3개: 32~47줄, 가장 긴 줄 약 1,100자, 전체 1,500~3,300자
MAX_TEXT_BLOCKS = 200
MAX_BLOCK_CHARS = 2000
MAX_TEXT_CHARS = 20000
# 화면에 안 보이는 문자: C0·C1 제어 문자(줄바꿈·탭 제외), 폭 0 문자, 글자 방향 바꾸기, BOM
_INVISIBLE_RE = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")

T = TypeVar("T")


class BlockedUrlError(ValueError):
    """사이트 도메인 밖 주소로 요청하려 한 경우 (처음 주소·리다이렉트 모두). 요청은 보내지 않음."""


class PageTooLargeError(ValueError):
    """상품 페이지 응답이 크기 상한을 넘은 경우."""


def matches_domain(host: str | None, domains: Iterable[str]) -> bool:
    """호스트가 도메인 자체이거나 그 하위 도메인인지. 흉내 도메인(made-in-china.com.evil.example)은 아님.

    Args:
        host: 주소의 호스트.
        domains: 허용 도메인.

    Returns:
        bool: 허용 도메인에 속하면 True.
    """
    host = (host or "").lower().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


class MarketplaceBaseClient(BaseClient[ProductPageRequest, ProductPage]):
    """판매 사이트 상품 페이지 클라이언트 공통 베이스.

    방식 : GET/HTML
    서비스 키 : 불필요. 단, 브라우저 헤더 필수.
    비고
        판매자마다 하위 도메인이 달라 base_url 없이 상품 주소 전체로 요청.
        하위 클라이언트는 `SITE`·`DOMAINS`·`IMAGE_DOMAINS`·`_parse_page`만 구현.
        형식 변환만 하고 이미지 고르기는 쓰는 쪽.
    """

    SITE: ClassVar[str]
    # 상품 페이지 도메인 (하위 도메인 포함). 리다이렉트도 이 안에서만 따라감
    DOMAINS: ClassVar[tuple[str, ...]]
    # 이미지 서버 도메인. 이 밖의 이미지 주소는 버림
    IMAGE_DOMAINS: ClassVar[tuple[str, ...]]

    def __init__(self):
        super().__init__(
            base_url="",
            timeout=15.0,
            # 헤더 없으면 아마존은 차단 페이지(3.7KB)를 돌려줌 (#322)
            headers={"User-Agent": _BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"},
        )

    def _send(self, request: ProductPageRequest) -> httpx.Response:
        """상품 페이지 HTML을 받는다. 리다이렉트는 사이트 도메인 안에서만 직접 따라감.

        Args:
            request: 상품 페이지 조회 요청.

        Returns:
            httpx.Response: HTML 원문 응답.

        Raises:
            BlockedUrlError: 처음 주소나 리다이렉트 주소가 사이트 도메인 밖인 경우. 그 주소로는 요청하지 않음.
            PageTooLargeError: 응답이 MAX_PAGE_BYTES를 넘은 경우.
            httpx.TooManyRedirects: 리다이렉트가 MAX_REDIRECTS번을 넘은 경우.
            httpx.HTTPStatusError: 4xx/5xx 응답인 경우.
        """
        url = httpx.URL(request.url)
        for _ in range(MAX_REDIRECTS + 1):
            self._check_allowed(url)
            with self._client.stream("GET", url) as response:
                if response.is_redirect and response.next_request is not None:
                    url = response.next_request.url
                    continue
                response.raise_for_status()
                return self._read_limited(response)
        raise httpx.TooManyRedirects(f"리다이렉트가 {MAX_REDIRECTS}번을 넘었습니다: {request.url}")

    def _check_allowed(self, url: httpx.URL) -> None:
        """http(s)이고 사이트 도메인 안인 주소만 통과. 내부망·메타데이터 주소도 여기서 막힘."""
        if url.scheme not in ("http", "https") or not matches_domain(url.host, self.DOMAINS):
            raise BlockedUrlError(f"{self.SITE} 도메인 밖 주소로는 요청하지 않습니다: {url.host or url}")

    @staticmethod
    def _read_limited(response: httpx.Response) -> httpx.Response:
        """본문을 크기 상한까지만 읽어 완성된 응답으로 돌려준다. 넘으면 읽다가 끊음."""
        body = bytearray()
        for chunk in response.iter_bytes():
            body += chunk
            if len(body) > MAX_PAGE_BYTES:
                raise PageTooLargeError(f"상품 페이지가 {MAX_PAGE_BYTES}바이트를 넘었습니다: {response.url}")
        # 압축은 이미 풀었으므로 본문 형식(문자셋)만 넘김
        headers = {"content-type": response.headers.get("content-type", "text/html")}
        return httpx.Response(response.status_code, headers=headers, content=bytes(body), request=response.request)

    def _parse(self, raw: httpx.Response) -> ProductPage:
        """사이트별 파싱 결과에 공통 안전 규칙을 적용한다. 하위 클라이언트는 _parse_page만 구현.

        Args:
            raw: 상품 페이지 HTML 응답.

        Returns:
            ProductPage: 이미지 서버 밖 주소를 빼고 판매자 글을 정리·상한 적용한 결과.
        """
        page = self._parse_page(raw)
        text_blocks, truncated = _limit_text(page.text_blocks)
        title = _INVISIBLE_RE.sub("", page.title or "").strip()
        return page.model_copy(update={
            "title": title or None,
            "text_blocks": text_blocks,
            "text_truncated": truncated,
            "images": [image for image in page.images if self._allowed_image(image)],
        })

    def _parse_page(self, raw: httpx.Response) -> ProductPage:
        """상품 페이지 HTML을 판매자 글과 이미지로 바꾼다 (사이트별 구현).

        Args:
            raw: 상품 페이지 HTML 응답.

        Returns:
            ProductPage: 상품명·판매자 글·이미지.
        """
        raise NotImplementedError

    def _allowed_image(self, image: ProductPageImage) -> bool:
        """원본·썸네일 주소가 모두 이미지 서버의 https 주소인지. 형식이 깨진 주소는 버림."""
        try:
            urls = [httpx.URL(address) for address in (image.url, image.thumbnail_url)]
        except httpx.InvalidURL:
            return False
        return all(url.scheme == "https" and matches_domain(url.host, self.IMAGE_DOMAINS) for url in urls)

    def parse_html(self, url: str, html: str) -> ProductPage:
        """저장해 둔 상품 페이지 HTML을 받은 페이지와 같은 규칙으로 읽는다. 요청은 보내지 않음.

        같은 입력으로 다시 재거나, 사이트가 응답하지 않을 때 실험·리뷰에서 재현할 때 씀.

        Args:
            url: 그 HTML을 받은 상품 페이지 주소.
            html: 상품 페이지 HTML.

        Returns:
            ProductPage: 상품명·판매자 글·이미지.

        Raises:
            BlockedUrlError: 주소가 사이트 도메인 밖인 경우.
        """
        self._check_allowed(httpx.URL(url))
        return self._parse(httpx.Response(200, text=html, request=httpx.Request("GET", url)))

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


def _limit_text(blocks: list[str]) -> tuple[list[str], bool]:
    """보이지 않는 문자를 지우고 줄 수·줄 길이·전체 길이 상한까지만 남긴다. 페이지 앞쪽(상품명·사양)부터 남김.

    Args:
        blocks: 판매자 글.

    Returns:
        tuple[list[str], bool]: (정리한 글, 상한 때문에 잘랐는지).
    """
    limited: list[str] = []
    total = 0
    truncated = False
    for block in blocks:
        text = _INVISIBLE_RE.sub("", block).strip()
        if not text:
            continue
        if len(limited) == MAX_TEXT_BLOCKS or total >= MAX_TEXT_CHARS:
            truncated = True
            break
        room = min(MAX_BLOCK_CHARS, MAX_TEXT_CHARS - total)
        if len(text) > room:
            text, truncated = text[:room], True
        limited.append(text)
        total += len(text)
    return limited, truncated
