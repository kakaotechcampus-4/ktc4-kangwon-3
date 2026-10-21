"""상품 주소 하나로 추출 입력(ExtractionInput)을 만든다.

수집(판매 사이트 클라이언트) → 이미지 방식에 따라 이미지 고르기 → 추출 입력.
    - none: 이미지 없이 판매자 글만
    - selected: 후보 이미지를 썸네일로 분류(ImageTriageAgent)해 사양·인증·포장만
    - all: 분류 없이 후보 이미지 전부 (상한까지)
클라이언트는 형식 변환만, 분류 에이전트는 분류만 하고 이미지를 쓸지·몇 장을 넘길지는 여기서 정함.
파이프라인(CompliancePipeline) 연결 전 실험 단계 (#320 이후 연결).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from ..agents.image_triage import MAX_IMAGES as MAX_TRIAGE_IMAGES
from ..agents.image_triage import ImageTriageAgent, ImageTriageInput
from ..clients.marketplace import MadeInChinaClient, MarketplaceBaseClient, matches_domain
from ..schemas.agent import ExtractionInput, ImageCategory, ImageTriageResponse
from ..schemas.clients.marketplace_request import ProductPageRequest
from ..schemas.clients.marketplace_response import ProductPage, ProductPageImage
from .errors import UnsupportedSiteError

# 추출에 넣을 이미지 방식. 사이트마다 페이지·이미지 성격이 달라 사이트별로 정함
ImagePolicy = Literal["none", "selected", "all"]


@dataclass(frozen=True)
class SiteConfig:
    """수집할 판매 사이트 하나.

    Attributes:
        client: 상품 페이지 클라이언트 생성 함수.
        images: 추출에 넣을 이미지 방식.
    """

    client: Callable[[], MarketplaceBaseClient]
    images: ImagePolicy


# 도메인 → 사이트. 도메인은 클라이언트의 DOMAINS (판매자 하위 도메인 포함)
SITES: Mapping[str, SiteConfig] = {
    # 사양·인증이 글로 충실해 글만. 이미지를 넣으면 chemical_product 등 판정이 흔들림 (3개 상품 비교 실험)
    **{domain: SiteConfig(MadeInChinaClient, images="none") for domain in MadeInChinaClient.DOMAINS},
}
# selected에서 넘길 분류. 판정에 쓸 글자가 있는 이미지
KEEP_CATEGORIES = frozenset({ImageCategory.SPECIFICATION, ImageCategory.CERTIFICATION, ImageCategory.PACKAGE})
# selected에서 넘기는 이미지 상한 (대표 이미지 포함)
MAX_IMAGES = 8
# all에서 넘기는 이미지 상한. 넘는 페이지는 앞에서부터
MAX_ALL_IMAGES = 50


@dataclass(frozen=True)
class UrlSource:
    """상품 주소 하나를 처리한 단계별 결과. 실험 러너가 단계마다 저장할 수 있게 같이 돌려줌.

    Attributes:
        page: 수집한 상품 페이지.
        images: 적용한 이미지 방식.
        triage: 후보 이미지 분류. selected가 아니면 분류하지 않아 빈 결과.
        selected: 추출에 넘긴 이미지. 넘기는 순서대로.
        extraction_input: 추출 에이전트 입력.
    """

    page: ProductPage
    images: ImagePolicy
    triage: ImageTriageResponse
    selected: list[ProductPageImage]
    extraction_input: ExtractionInput


class UrlSourceBuilder:
    """상품 주소로 페이지를 받아 사이트의 이미지 방식대로 추출 입력을 만든다.

    Args:
        triage_agent: 이미지 분류 에이전트. None이면 selected일 때 처음 쓸 때 기본 프로필로 생성.
        sites: 도메인 → 사이트. 테스트에서 가짜 클라이언트를 넣을 때 주입.
        images: 모든 사이트에 쓸 이미지 방식. None이면 사이트 설정대로 (실험에서 바꿔 볼 때 지정).
    """

    def __init__(
        self,
        triage_agent: ImageTriageAgent | None = None,
        *,
        sites: Mapping[str, SiteConfig] = SITES,
        images: ImagePolicy | None = None,
    ) -> None:
        self._triage_agent = triage_agent
        self._sites = sites
        self._images = images

    def build(self, url: str, *, product_id: str) -> UrlSource:
        """상품 주소 하나를 추출 입력으로 만든다.

        Args:
            url: 상품 페이지 주소.
            product_id: 추출 입력의 상품 ID. 분류 사용량 기록 대상 ID로도 씀.

        Returns:
            UrlSource: 수집·분류·고른 이미지·추출 입력.

        Raises:
            UnsupportedSiteError: 수집할 수 없는 사이트 주소인 경우.
            httpx.HTTPError: 페이지를 받지 못한 경우.
            ImageTriageFailedError: 이미지 분류 실패.
        """
        site = site_for(url, self._sites)
        client = site.client()
        try:
            page = client.fetch_parsed(ProductPageRequest(url=url))
        finally:
            client.close()
        return self._from_page(page, product_id, self._images or site.images)

    def build_from_html(self, url: str, html: str, *, product_id: str) -> UrlSource:
        """저장해 둔 상품 페이지 HTML로 추출 입력을 만든다. 페이지 요청은 보내지 않음.

        같은 입력으로 다시 재거나, 사이트가 응답하지 않을 때 실험·리뷰에서 재현할 때 씀.
        이미지는 주소만 넘겨 분류·추출 때 모델 쪽이 받음.

        Args:
            url: 그 HTML을 받은 상품 페이지 주소. 사이트 고르기와 출처 표시에 씀.
            html: 상품 페이지 HTML.
            product_id: 추출 입력의 상품 ID. 분류 사용량 기록 대상 ID로도 씀.

        Returns:
            UrlSource: 수집·분류·고른 이미지·추출 입력.

        Raises:
            UnsupportedSiteError: 수집할 수 없는 사이트 주소인 경우.
            ImageTriageFailedError: 이미지 분류 실패.
        """
        site = site_for(url, self._sites)
        client = site.client()
        try:
            page = client.parse_html(url, html)
        finally:
            client.close()
        return self._from_page(page, product_id, self._images or site.images)

    def _from_page(self, page: ProductPage, product_id: str, images: ImagePolicy) -> UrlSource:
        """이미지 방식대로 넘길 이미지를 골라 추출 입력을 만든다. 분류는 selected일 때만."""
        triage = ImageTriageResponse(items=[])
        if images == "selected":
            if self._triage_agent is None:
                self._triage_agent = ImageTriageAgent()
            # 분류 한도를 넘는 후보는 앞에서부터 한도까지만. 분류 안 된 뒤쪽 이미지는 select_images가 넘기지 않음
            triage = self._triage_agent.run(ImageTriageInput(
                image_urls=[image.thumbnail_url for image in page.images[:MAX_TRIAGE_IMAGES]], subject_id=product_id,
            ))
            selected = select_images(page, triage)
        elif images == "all":
            selected = page.images[:MAX_ALL_IMAGES]
        else:
            selected = []
        return UrlSource(
            page=page,
            images=images,
            triage=triage,
            selected=selected,
            extraction_input=ExtractionInput(
                product_id=product_id,
                source_url=page.source_url,
                text_blocks=page.text_blocks,
                image_urls=[image.url for image in selected],
            ),
        )


def site_for(url: str, sites: Mapping[str, SiteConfig] = SITES) -> SiteConfig:
    """주소의 도메인으로 사이트를 고른다. 판매자 하위 도메인도 같은 사이트로 봄.

    Args:
        url: 상품 페이지 주소.
        sites: 도메인 → 사이트.

    Returns:
        SiteConfig: 사이트의 클라이언트·이미지 방식.

    Raises:
        UnsupportedSiteError: 수집할 수 없는 사이트 주소인 경우.
    """
    host = urlparse(url).hostname or ""
    for domain, site in sites.items():
        if matches_domain(host, [domain]):
            return site
    raise UnsupportedSiteError(f"수집할 수 없는 판매 사이트입니다: {host or url}")


def client_for(url: str, sites: Mapping[str, SiteConfig] = SITES) -> MarketplaceBaseClient:
    """주소의 사이트 클라이언트를 새로 만든다. 다 쓰면 close().

    Raises:
        UnsupportedSiteError: 수집할 수 없는 사이트 주소인 경우.
    """
    return site_for(url, sites).client()


def select_images(page: ProductPage, triage: ImageTriageResponse) -> list[ProductPageImage]:
    """추출에 넘길 이미지를 고른다.

    대표 이미지(첫 갤러리 사진) + 사양·인증·포장 이미지를 페이지 순서대로, 최대 MAX_IMAGES장.
    대표 이미지는 썸네일에서 글자를 못 읽어 제품 사진으로 분류돼도 넘김 (포장 글자가 있는 경우가 많음).
    분류에 없는 번호(모델이 빠뜨린 이미지)는 넘기지 않음.

    Args:
        page: 수집한 상품 페이지.
        triage: page.images 순서(1부터)의 분류.

    Returns:
        list[ProductPageImage]: 넘기는 순서대로 고른 이미지.
    """
    categories = {item.index: item.category for item in triage.items}
    representative = next((index for index, image in enumerate(page.images, 1) if image.area == "gallery"), None)
    picked = [
        image for index, image in enumerate(page.images, 1)
        if index == representative or categories.get(index) in KEEP_CATEGORIES
    ]
    return picked[:MAX_IMAGES]
