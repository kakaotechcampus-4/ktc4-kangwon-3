"""상품 주소 → 수집 → 이미지 분류 → 추출 입력 조립을 가짜 클라이언트·가짜 분류로 확인한다."""

import pytest

from app.pipeline.errors import UnsupportedSiteError
from app.pipeline.url_source import (
    MAX_ALL_IMAGES, MAX_IMAGES, SITES, SiteConfig, UrlSourceBuilder, select_images,
)
from app.schemas.agent import ImageTriageItem, ImageTriageResponse
from app.schemas.clients.marketplace_response import ProductPage, ProductPageImage

URL = "https://seller.en.made-in-china.com/product/AbCd/China-Power-Bank.html"


def _image(name: str, area: str = "description") -> ProductPageImage:
    return ProductPageImage(url=f"https://img/{name}.jpg", thumbnail_url=f"https://img/{name}-small.jpg", area=area)


def _page(*images: ProductPageImage) -> ProductPage:
    return ProductPage(source_url=URL, site="made_in_china", title="보조배터리", text_blocks=["보조배터리", "Capacity: 10000mAh"],
                       images=list(images))


def _triage(*categories: str | None) -> ImageTriageResponse:
    # None은 모델이 빠뜨린 번호
    return ImageTriageResponse(items=[ImageTriageItem(index=index, category=category)
                                      for index, category in enumerate(categories, 1) if category])


def _sites(make_client, images: str = "selected") -> dict[str, SiteConfig]:
    return {"made-in-china.com": SiteConfig(make_client, images=images)}


class _FakeClient:
    def __init__(self, page: ProductPage) -> None:
        self.page = page
        self.requested: list[str] = []
        self.closed = False

    def fetch_parsed(self, request):
        self.requested.append(request.url)
        return self.page

    def close(self) -> None:
        self.closed = True


class _FakeTriage:
    def __init__(self, response: ImageTriageResponse) -> None:
        self.response = response
        self.calls: list[tuple[list[str], str]] = []

    def run(self, input):
        self.calls.append((input.image_urls, input.subject_id))
        return self.response


def test_사양_인증_포장과_대표_이미지만_페이지_순서대로_고른다():
    page = _page(_image("main", "gallery"), _image("angle", "gallery"), _image("spec"), _image("banner"),
                 _image("cert"), _image("box"), _image("scene"))

    selected = select_images(page, _triage("product", "product", "specification", "unrelated",
                                           "certification", "package", "lifestyle"))

    # 대표(첫 갤러리)는 제품 사진으로 분류돼도 넘김
    assert [image.url for image in selected] == [
        "https://img/main.jpg", "https://img/spec.jpg", "https://img/cert.jpg", "https://img/box.jpg"]


def test_모델이_빠뜨린_이미지는_넘기지_않는다():
    page = _page(_image("main", "gallery"), _image("unknown"), _image("spec"))

    assert [image.url for image in select_images(page, _triage(None, None, "specification"))] == [
        "https://img/main.jpg", "https://img/spec.jpg"]


def test_넘기는_이미지는_대표_포함_상한까지만():
    page = _page(_image("main", "gallery"), *(_image(f"spec{n}") for n in range(MAX_IMAGES + 2)))

    selected = select_images(page, _triage("product", *["specification"] * (MAX_IMAGES + 2)))

    assert len(selected) == MAX_IMAGES
    assert selected[0].url == "https://img/main.jpg"


def test_갤러리가_없으면_대표_없이_고른다():
    page = _page(_image("spec"), _image("scene"))

    selected = select_images(page, _triage("specification", "lifestyle"))

    assert [image.url for image in selected] == ["https://img/spec.jpg"]


def test_주소로_받은_페이지를_썸네일로_분류하고_고른_원본_주소로_추출_입력을_만든다():
    page = _page(_image("main", "gallery"), _image("spec"), _image("banner"))
    client, triage = _FakeClient(page), _FakeTriage(_triage("product", "specification", "unrelated"))
    builder = UrlSourceBuilder(triage, sites=_sites(lambda: client))

    source = builder.build(URL, product_id="p-1")

    assert (client.requested, client.closed) == ([URL], True)
    # 분류는 썸네일, 추출은 원본
    thumbnails = ["https://img/main-small.jpg", "https://img/spec-small.jpg", "https://img/banner-small.jpg"]
    assert triage.calls == [(thumbnails, "p-1")]
    assert source.extraction_input.model_dump() == {
        "product_id": "p-1", "source_url": URL, "text_blocks": ["보조배터리", "Capacity: 10000mAh"],
        "image_urls": ["https://img/main.jpg", "https://img/spec.jpg"],
    }
    assert (source.page, source.triage) == (page, triage.response)


def test_페이지를_받다_실패해도_클라이언트를_닫는다():
    class _BrokenClient(_FakeClient):
        def fetch_parsed(self, request):
            raise RuntimeError("403")

    client = _BrokenClient(_page())
    builder = UrlSourceBuilder(_FakeTriage(_triage()), sites=_sites(lambda: client))

    with pytest.raises(RuntimeError):
        builder.build(URL, product_id="p-1")
    assert client.closed


@pytest.mark.parametrize("url", [
    "https://www.amazon.com/dp/B079MDLGT8",
    "https://made-in-china.com.evil.example/product/x.html",
    "https://notmade-in-china.com/product/x.html",
])
def test_수집할_수_없는_사이트는_받지_않는다(url):
    builder = UrlSourceBuilder(_FakeTriage(_triage()), sites=_sites(lambda: pytest.fail("부르면 안 됨")))

    with pytest.raises(UnsupportedSiteError):
        builder.build(url, product_id="p-1")


def test_도메인_자체와_하위_도메인을_모두_받는다():
    page = _page()
    builder = UrlSourceBuilder(_FakeTriage(_triage()), sites=_sites(lambda: _FakeClient(page)))

    for url in ("https://made-in-china.com/product/x.html", "https://www.made-in-china.com/product/x.html"):
        assert builder.build(url, product_id="p-1").page is page


def test_저장한_HTML로도_같은_흐름으로_추출_입력을_만들고_페이지는_받지_않는다():
    page = _page(_image("main", "gallery"), _image("spec"))

    class _OfflineClient(_FakeClient):
        def fetch_parsed(self, request):
            pytest.fail("페이지를 받으면 안 됨")

        def parse_html(self, url, html):
            self.requested.append((url, html))
            return self.page

    client, triage = _OfflineClient(page), _FakeTriage(_triage("product", "specification"))
    builder = UrlSourceBuilder(triage, sites=_sites(lambda: client))

    source = builder.build_from_html(URL, "<html>저장본</html>", product_id="p-1")

    assert (client.requested, client.closed) == ([(URL, "<html>저장본</html>")], True)
    assert source.extraction_input.image_urls == ["https://img/main.jpg", "https://img/spec.jpg"]


def test_none이면_분류하지_않고_판매자_글만_넘긴다(monkeypatch):
    # 분류 에이전트(모델)도 만들지 않음
    monkeypatch.setattr("app.pipeline.url_source.ImageTriageAgent", lambda: pytest.fail("만들면 안 됨"))
    page = _page(_image("main", "gallery"), _image("spec"))
    builder = UrlSourceBuilder(sites=_sites(lambda: _FakeClient(page), images="none"))

    source = builder.build(URL, product_id="p-1")

    assert (source.images, source.triage.items, source.selected) == ("none", [], [])
    assert source.extraction_input.image_urls == []
    assert source.extraction_input.text_blocks == ["보조배터리", "Capacity: 10000mAh"]


def test_all이면_분류하지_않고_후보_이미지를_상한까지_넘긴다():
    page = _page(*(_image(f"img{n}") for n in range(MAX_ALL_IMAGES + 3)))
    triage = _FakeTriage(_triage())
    builder = UrlSourceBuilder(triage, sites=_sites(lambda: _FakeClient(page), images="all"))

    source = builder.build(URL, product_id="p-1")

    assert triage.calls == []
    assert source.extraction_input.image_urls == [f"https://img/img{n}.jpg" for n in range(MAX_ALL_IMAGES)]


def test_빌더에_이미지_방식을_주면_사이트_설정보다_우선한다():
    page = _page(_image("main", "gallery"), _image("spec"))
    triage = _FakeTriage(_triage("product", "specification"))
    builder = UrlSourceBuilder(triage, sites=_sites(lambda: _FakeClient(page), images="none"), images="selected")

    source = builder.build(URL, product_id="p-1")

    assert source.images == "selected"
    assert source.extraction_input.image_urls == ["https://img/main.jpg", "https://img/spec.jpg"]


def test_Made_in_China는_글만_쓴다():
    # 이미지를 넣으면 chemical_product 등 판정이 흔들림 (3개 상품 비교 실험)
    assert SITES["made-in-china.com"].images == "none"


def test_selected는_후보가_분류_한도를_넘으면_앞에서부터_한도까지만_분류한다():
    # 분류 에이전트는 한도를 넘으면 오류 → URL 진단 전체가 실패했음 (#337 리뷰)
    from app.agents.image_triage import MAX_IMAGES as MAX_TRIAGE_IMAGES

    page = _page(_image("main", "gallery"), *(_image(f"img{n}") for n in range(2, MAX_TRIAGE_IMAGES + 2)))

    class _LimitedTriage(_FakeTriage):
        def run(self, input):
            if len(input.image_urls) > MAX_TRIAGE_IMAGES:
                raise ValueError(f"이미지는 한 번에 {MAX_TRIAGE_IMAGES}장까지 분류합니다")
            return super().run(input)

    # 2번이 사양, 마지막(한도 밖) 이미지는 분류되지 않음
    triage = _LimitedTriage(_triage("product", "specification", *["lifestyle"] * (MAX_TRIAGE_IMAGES - 2)))
    builder = UrlSourceBuilder(triage, sites=_sites(lambda: _FakeClient(page)))

    source = builder.build(URL, product_id="p-1")

    [(classified, _)] = triage.calls
    assert len(page.images) == MAX_TRIAGE_IMAGES + 1
    assert classified == [image.thumbnail_url for image in page.images[:MAX_TRIAGE_IMAGES]]
    assert source.extraction_input.image_urls == ["https://img/main.jpg", "https://img/img2.jpg"]
