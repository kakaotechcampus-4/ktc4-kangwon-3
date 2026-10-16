"""Made-in-China 상품 페이지 클라이언트를 실제 호출 없이 검증한다.

입력은 실제 페이지에서 구조(JSON-LD·Product Highlights·.rich-text)만 남긴 뼈대 HTML. 상용 원문은 넣지 않음.
"""

import json

import httpx
import pytest

from app.clients.marketplace import MadeInChinaClient
from app.schemas.clients.marketplace_request import ProductPageRequest

URL = "https://seller.en.made-in-china.com/product/AbCd/China-Power-Bank.html"
_LD = {
    "@context": "https://schema.org", "@type": "Product", "name": "JSON-LD 상품명",
    "image": [
        "https://image.made-in-china.com/2f0j00GalA/Power-Bank.webp",
        "https://image.made-in-china.com/2f0j00GalB/Power-Bank.webp",
    ],
    "additionalProperty": [
        {"@type": "PropertyValue", "name": "Capacity", "value": "10000mAh"},
        {"@type": "PropertyValue", "name": "Certification", "value": "CE, RoHS"},
        {"@type": "PropertyValue", "name": "Empty", "value": ""},
    ],
}


def _page(*, ld=_LD, rich: str = "", h1: str = "<h1>10000mAh Power Bank</h1>") -> str:
    ld_script = f'<script type="application/ld+json">{json.dumps(ld)}</script>' if ld else ""
    return f"""<html><head>
      <script type="application/ld+json">{{"@type": "BreadcrumbList"}}</script>{ld_script}
    </head><body>{h1}
      <ul><li class="highlight-item-pc">Comprehensive Certifications: KC, PSE, CE.</li></ul>
      <div class="rich-text cf">{rich}</div>
      <div class="sr-layout-footer"><img src="//image.made-in-china.com/205f0j00Logo/Company-Co-Ltd-.jpg"></div>
    </body></html>"""


def _parse(wire, html: str):
    client = MadeInChinaClient()
    wire(client, lambda request: httpx.Response(200, text=html))
    return client.fetch_parsed(ProductPageRequest(url=URL))


_RICH = """
  <h3>Product Parameters</h3>
  <table><tr><td><p>Input</p></td><td><p>5V/2A</p></td></tr><tr><td>Output</td><td></td></tr></table>
  <ul><li><p>Overcharge protection</p></li></ul>
  <p>Detailed Photos</p>
  <img data-original="//image.made-in-china.com/226f3j00DescA/Power-Bank.jpg" src="//www.micstatic.com/athena/img/transparent.png">
  <img src="//www.micstatic.com/athena/img/transparent.png">
  <img data-original="//image.made-in-china.com/226f3j00GalA/Power-Bank.jpg">
"""


def test_상품명_하이라이트_사양표_상세_설명을_페이지_순서대로_글로_꺼낸다(wire):
    page = _parse(wire, _page(rich=_RICH))

    assert (page.site, page.title, page.source_url) == ("made_in_china", "10000mAh Power Bank", URL)
    assert page.text_blocks == [
        "10000mAh Power Bank",
        "Comprehensive Certifications: KC, PSE, CE.",
        # 사양표는 JSON-LD additionalProperty, 값 없는 줄은 뺌
        "Capacity: 10000mAh",
        "Certification: CE, RoHS",
        "Product Parameters",
        # 표는 행마다 한 줄, 칸 안 문단은 다시 넣지 않음
        "Input | 5V/2A",
        "Output",
        "Overcharge protection",
        "Detailed Photos",
    ]


def test_갤러리는_JSON_LD_이미지에서_550px_썸네일_주소를_만든다(wire):
    page = _parse(wire, _page())

    assert [(image.area, image.url, image.thumbnail_url) for image in page.images] == [
        ("gallery", "https://image.made-in-china.com/2f0j00GalA/Power-Bank.webp",
         "https://image.made-in-china.com/202f0j00GalA/Power-Bank.webp"),
        ("gallery", "https://image.made-in-china.com/2f0j00GalB/Power-Bank.webp",
         "https://image.made-in-china.com/202f0j00GalB/Power-Bank.webp"),
    ]


def test_상세_설명_이미지는_지연_로딩_주소를_쓰고_같은_사진과_회사_로고는_넣지_않는다(wire):
    page = _parse(wire, _page(rich=_RICH))

    description = [image for image in page.images if image.area == "description"]
    # 자리표시만 있는 이미지는 빼고, 갤러리와 사진 ID가 같은 GalA는 한 번만
    assert [(image.url, image.thumbnail_url) for image in description] == [
        ("https://image.made-in-china.com/226f3j00DescA/Power-Bank.jpg",
         "https://image.made-in-china.com/226f3j00DescA/Power-Bank.jpg"),
    ]
    assert len(page.images) == 3
    assert all("Logo" not in image.url for image in page.images)


def test_JSON_LD나_상세_설명이_없어도_있는_것만_꺼낸다(wire):
    page = _parse(wire, _page(ld=None, h1="").replace('<div class="rich-text cf"></div>', ""))

    assert (page.title, page.text_blocks, page.images) == (None, ["Comprehensive Certifications: KC, PSE, CE."], [])


def test_h1이_없으면_JSON_LD_상품명을_쓴다(wire):
    page = _parse(wire, _page(h1=""))

    assert page.title == "JSON-LD 상품명"
    assert page.text_blocks[0] == "JSON-LD 상품명"


def test_저장한_HTML도_받은_페이지와_같은_규칙으로_읽고_요청은_보내지_않는다(wire):
    client = MadeInChinaClient()
    sent = wire(client, lambda request: pytest.fail("요청을 보내면 안 됨"))
    html = _page(rich=_RICH)

    page = client.parse_html(URL, html)

    assert sent == []
    assert page == _parse(wire, html)
