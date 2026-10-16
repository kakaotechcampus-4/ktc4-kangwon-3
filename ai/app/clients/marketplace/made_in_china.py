"""Made-in-China 상품 페이지 클라이언트."""

import json
import re

import httpx
from bs4 import BeautifulSoup, Tag

from ...schemas.clients.marketplace_response import ProductPage, ProductPageImage
from .base import MarketplaceBaseClient

# 이미지 주소: //image.made-in-china.com/{크기}j00{사진 ID}/{이름}.{확장자}
_IMAGE_RE = re.compile(r"^(?:https?:)?//image\.made-in-china\.com/(\w+?)j00(\w+)/")
# 갤러리 원본(1276px)과 같은 사진의 550px
_GALLERY_FULL, _GALLERY_THUMBNAIL = "2f0j00", "202f0j00"
# 상세 설명 이미지 지연 로딩 자리표시
_PLACEHOLDER = "transparent.png"
_TEXT_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "tr"]


class MadeInChinaClient(MarketplaceBaseClient):
    """Made-in-China(수출 B2B 도매) 상품 페이지.

    방식 : GET/HTML (요청만으로 상품명·사양표·상세 설명이 옴, #322)
    비고
        글: 상품명(h1), Product Highlights(판매자 편집 블록), 사양표(JSON-LD additionalProperty),
            판매자 상세 설명(.rich-text, 표는 행마다 한 줄).
        이미지: 갤러리(JSON-LD Product.image)·상세 설명(.rich-text의 data-original).
            영상 표지·회사 로고는 두 영역에 없어 들어오지 않음.
        상세 설명 이미지는 작은 크기 주소를 찾지 못해 원본 주소를 썸네일로도 씀.
    """

    SITE = "made_in_china"

    def _parse(self, raw: httpx.Response) -> ProductPage:
        """상품 페이지 HTML을 판매자 글과 이미지로 바꾼다.

        Args:
            raw: 상품 페이지 HTML 응답.

        Returns:
            ProductPage: 상품명·판매자 글·이미지.
        """
        soup = self._soup(raw)
        product = _json_ld_product(soup)
        title = _text(soup.find("h1")) or product.get("name")
        rich = soup.select_one(".rich-text")

        text_blocks = [
            *([title] if title else []),
            *(_text(item) for item in soup.select(".highlight-item-pc")),
            *(f"{prop['name']}: {prop['value']}" for prop in product.get("additionalProperty", [])
              if prop.get("name") and prop.get("value")),
            *(_rich_text_lines(rich) if rich else []),
        ]
        images = [*_gallery_images(product), *(_description_images(rich) if rich else [])]
        return ProductPage(
            source_url=str(raw.url),
            site=self.SITE,
            title=title,
            text_blocks=[block for block in text_blocks if block],
            images=self._unique(images, key=_photo_id),
        )


def _text(element: Tag | None) -> str:
    """태그 안 글을 공백 하나로 이어 붙인다. 없으면 빈 문자열."""
    return element.get_text(" ", strip=True) if element else ""


def _json_ld_product(soup: BeautifulSoup) -> dict:
    """JSON-LD 중 @type이 Product인 것. 없으면 빈 dict."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            return data
    return {}


def _rich_text_lines(rich: Tag) -> list[str]:
    """상세 설명 글. 문단은 한 줄씩, 표는 행마다 칸을 ' | '로 이어 한 줄."""
    lines = []
    for element in rich.find_all(_TEXT_TAGS):
        if element.name == "tr":
            cells = [_text(cell) for cell in element.find_all(["td", "th"])]
            lines.append(" | ".join(cell for cell in cells if cell))
        # 표 안 문단은 행으로 이미 넣음. 중첩된 목록·문단은 바깥 것만
        elif not element.find_parent("tr") and not element.find_parent(_TEXT_TAGS):
            lines.append(_text(element))
    return lines


def _absolute(url: str) -> str:
    """//로 시작하는 주소에 https를 붙인다."""
    return f"https:{url}" if url.startswith("//") else url


def _gallery_images(product: dict) -> list[ProductPageImage]:
    """갤러리 사진. 원본 주소의 크기 부분만 바꿔 550px 썸네일을 만듦."""
    urls = product.get("image") or []
    return [
        ProductPageImage(url=url, thumbnail_url=url.replace(f"/{_GALLERY_FULL}", f"/{_GALLERY_THUMBNAIL}", 1),
                         area="gallery")
        for url in map(_absolute, [urls] if isinstance(urls, str) else urls)
    ]


def _description_images(rich: Tag) -> list[ProductPageImage]:
    """상세 설명 이미지. 지연 로딩이라 실제 주소는 data-original."""
    images = []
    for img in rich.find_all("img"):
        url = img.get("data-original") or img.get("src") or ""
        if url and _PLACEHOLDER not in url:
            url = _absolute(url)
            images.append(ProductPageImage(url=url, thumbnail_url=url, area="description"))
    return images


def _photo_id(image: ProductPageImage) -> str:
    """같은 사진을 가리는 키. 크기만 다른 주소는 사진 ID가 같음."""
    match = _IMAGE_RE.match(image.url)
    return match.group(2) if match else image.url
