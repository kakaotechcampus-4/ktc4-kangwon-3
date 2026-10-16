"""판매 사이트 상품 페이지 클라이언트 공통 베이스를 실제 호출 없이 검증한다."""

import httpx
import pytest
from pydantic import ValidationError

from app.clients.marketplace import MarketplaceBaseClient
from app.schemas.clients.marketplace_request import ProductPageRequest
from app.schemas.clients.marketplace_response import ProductPage

URL = "https://yuntan.en.made-in-china.com/product/jZbflYzyZctU/China-Power-Bank.html"


class _TitleClient(MarketplaceBaseClient):
    """제목만 꺼내는 시험용 하위 클라이언트."""

    SITE = "test_site"

    def _parse(self, raw):
        soup = self._soup(raw)
        return ProductPage(source_url=str(raw.request.url), site=self.SITE, title=soup.title.get_text(strip=True))


def test_상품_주소_전체로_브라우저_헤더를_붙여_요청한다(wire):
    client = _TitleClient()
    sent = wire(client, lambda request: httpx.Response(200, text="<title>보조배터리</title>"))

    page = client.fetch_parsed(ProductPageRequest(url=URL))

    assert str(sent[0].url) == URL
    # 헤더 없으면 아마존은 차단 페이지 (#322)
    assert sent[0].headers["User-Agent"].startswith("Mozilla/5.0")
    assert sent[0].headers["Accept-Language"].startswith("en")
    assert (page.site, page.title) == ("test_site", "보조배터리")


def test_다른_주소로_넘겨주면_따라가서_받는다(wire):
    moved = "https://www.made-in-china.com/product/moved.html"
    client = _TitleClient()

    def handler(request):
        if str(request.url) == URL:
            return httpx.Response(301, headers={"Location": moved})
        return httpx.Response(200, text="<title>옮긴 페이지</title>")

    sent = wire(client, handler)

    assert client.fetch_parsed(ProductPageRequest(url=URL)).source_url == moved
    assert [str(request.url) for request in sent] == [URL, moved]


def test_4xx_5xx는_예외로_알린다(wire):
    client = _TitleClient()
    wire(client, lambda request: httpx.Response(403, text="blocked"))

    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_raw(ProductPageRequest(url=URL))


@pytest.mark.parametrize("url", ["", "made-in-china.com/product/x.html", "ftp://made-in-china.com/x", "https:// x"])
def test_http_https_전체_주소가_아니면_요청하지_않는다(url):
    with pytest.raises(ValidationError):
        ProductPageRequest(url=url)


def test_같은_키는_처음_것만_순서대로_남긴다():
    items = ["a-1", "b-1", "a-2", "c-1", "b-2"]

    assert MarketplaceBaseClient._unique(items, key=lambda item: item[0]) == ["a-1", "b-1", "c-1"]
