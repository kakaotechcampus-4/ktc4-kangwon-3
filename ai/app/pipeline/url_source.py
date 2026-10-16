"""상품 주소 하나로 추출 입력(ExtractionInput)을 만든다.

수집(판매 사이트 클라이언트) → 후보 이미지 분류(ImageTriageAgent) → 남길 이미지 고르기 → 추출 입력.
클라이언트는 형식 변환만, 분류 에이전트는 분류만 하고 몇 장을 어떤 순서로 넘길지는 여기서 정함.
파이프라인(CompliancePipeline) 연결 전 실험 단계 (#320 이후 연결).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

from ..agents.image_triage import ImageTriageAgent
from ..clients.marketplace import MadeInChinaClient, MarketplaceBaseClient
from ..schemas.agent import ExtractionInput, ImageCategory, ImageTriageResponse
from ..schemas.clients.marketplace_request import ProductPageRequest
from ..schemas.clients.marketplace_response import ProductPage, ProductPageImage

# 도메인 → 클라이언트. 판매자마다 하위 도메인이 달라 끝부분으로 맞춤
CLIENTS: Mapping[str, Callable[[], MarketplaceBaseClient]] = {
    "made-in-china.com": MadeInChinaClient,
}
# 추출에 넘길 분류. 판정에 쓸 글자가 있는 이미지
KEEP_CATEGORIES = frozenset({ImageCategory.SPECIFICATION, ImageCategory.CERTIFICATION, ImageCategory.PACKAGE})
# 추출에 넘기는 이미지 상한 (대표 이미지 포함)
MAX_IMAGES = 8


class UnsupportedSiteError(ValueError):
    """수집할 수 없는 판매 사이트 주소."""


@dataclass(frozen=True)
class UrlSource:
    """상품 주소 하나를 처리한 단계별 결과. 실험 러너가 단계마다 저장할 수 있게 같이 돌려줌.

    Attributes:
        page: 수집한 상품 페이지.
        triage: 후보 이미지 분류.
        selected: 추출에 넘긴 이미지. 넘기는 순서대로.
        extraction_input: 추출 에이전트 입력.
    """

    page: ProductPage
    triage: ImageTriageResponse
    selected: list[ProductPageImage]
    extraction_input: ExtractionInput


class UrlSourceBuilder:
    """상품 주소로 페이지를 받아 고른 이미지와 함께 추출 입력을 만든다.

    Args:
        triage_agent: 이미지 분류 에이전트. None이면 기본 프로필로 생성.
        clients: 도메인 → 클라이언트 생성 함수. 테스트에서 가짜 클라이언트를 넣을 때 주입.
    """

    def __init__(
        self,
        triage_agent: ImageTriageAgent | None = None,
        *,
        clients: Mapping[str, Callable[[], MarketplaceBaseClient]] = CLIENTS,
    ) -> None:
        self._triage_agent = triage_agent or ImageTriageAgent()
        self._clients = clients

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
        client = client_for(url, self._clients)
        try:
            page = client.fetch_parsed(ProductPageRequest(url=url))
        finally:
            client.close()
        return self._from_page(page, product_id)

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
        client = client_for(url, self._clients)
        try:
            page = client.parse_html(url, html)
        finally:
            client.close()
        return self._from_page(page, product_id)

    def _from_page(self, page: ProductPage, product_id: str) -> UrlSource:
        """수집한 페이지의 이미지를 분류하고 골라 추출 입력을 만든다."""
        triage = self._triage_agent.classify([image.thumbnail_url for image in page.images], subject_id=product_id)
        selected = select_images(page, triage)
        return UrlSource(
            page=page,
            triage=triage,
            selected=selected,
            extraction_input=ExtractionInput(
                product_id=product_id,
                source_url=page.source_url,
                text_blocks=page.text_blocks,
                image_urls=[image.url for image in selected],
            ),
        )


def client_for(
    url: str, clients: Mapping[str, Callable[[], MarketplaceBaseClient]] = CLIENTS,
) -> MarketplaceBaseClient:
    """주소의 도메인으로 클라이언트를 고른다. 판매자 하위 도메인도 같은 사이트로 봄.

    Args:
        url: 상품 페이지 주소.
        clients: 도메인 → 클라이언트 생성 함수.

    Returns:
        MarketplaceBaseClient: 새 클라이언트. 다 쓰면 close().

    Raises:
        UnsupportedSiteError: 수집할 수 없는 사이트 주소인 경우.
    """
    host = urlparse(url).hostname or ""
    for domain, make_client in clients.items():
        if host == domain or host.endswith(f".{domain}"):
            return make_client()
    raise UnsupportedSiteError(f"수집할 수 없는 판매 사이트입니다: {host or url}")


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
