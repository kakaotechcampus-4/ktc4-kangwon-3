"""수집 북마클릿이 내려 준 JSON을 상품 폴더로 푸는 스크립트를 검증한다 (#567).

이미지 다운로드는 가짜 fetch를 주입해 실제 요청 없이 확인한다.
"""

import importlib.util
import json
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).parents[2] / "scripts" / "collect" / "download_listing.py"
_spec = importlib.util.spec_from_file_location("download_listing", _MODULE_PATH)
download_listing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(download_listing)

detail_range = download_listing.detail_range
keep_image = download_listing.keep_image
normalize_image_url = download_listing.normalize_image_url
extension_of = download_listing.extension_of
export_listing = download_listing.export_listing
plan_batch = download_listing.plan_batch


def _image(top: int, *, width: int = 800, height: int = 800, alt: str = "", src: str = "https://img.kwcdn.com/product/fancy/a.jpg", lazy: bool = False) -> dict:
    return {"src": src, "width": width, "height": height, "top": top, "alt": alt, "lazy": lazy}


def _listing(site: str, *, text: str = "본문", images: list | None = None, markers: list | None = None, **extra) -> dict:
    return {
        "site": site,
        "url": f"https://{site}.example/item/1",
        "title": "제목",
        "collected_at": "2026-11-04T10:00:00.000Z",
        "text": text,
        "images": images or [],
        "markers": markers or [],
        **extra,
    }


# ── 상세 구역 계산 ──────────────────────────────────────────────────────────


def test_테무는_제품_세부_정보부터_관심_상품_둘러보기_전까지가_상세_구역이다():
    markers = [{"text": "제품 세부 정보", "top": 1705}, {"text": "상점 정보", "top": 1836}, {"text": "관심 상품 둘러보기", "top": 3823}, {"text": "인기 추천", "top": 4778}]

    assert detail_range("temu", markers) == (1705, 3823)


def test_영문_테무는_product_details부터_explore_your_interests_전까지가_상세_구역이다():
    markers = [{"text": "Product details", "top": 1900}, {"text": "Store Information", "top": 2100}, {"text": "Explore your interests", "top": 5600}]

    assert detail_range("temu", markers) == (1900, 5600)


def test_알리는_개요부터_그_아래_구매자_질문_전까지가_상세_구역이다():
    # "구매자 질문"이 개요 위에도 나올 수 있으므로(화면 탭 줄) 개요 아래 것만 끝으로 본다
    markers = [{"text": "구매자 질문", "top": 500}, {"text": "상품 정보", "top": 3966}, {"text": "개요", "top": 4980}, {"text": "구매자 질문", "top": 19306}]

    assert detail_range("aliexpress", markers) == (4980, 19306)


def test_표지가_없으면_페이지_전체가_상세_구역이다():
    low, high = detail_range("temu", [])

    assert low == 0
    assert high > 10**8


def test_직접_준_범위가_표지보다_우선한다():
    markers = [{"text": "제품 세부 정보", "top": 1705}, {"text": "관심 상품 둘러보기", "top": 3823}]

    assert detail_range("temu", markers, min_top=1000, max_top=2000) == (1000, 2000)


# ── 이미지 거르기 ──────────────────────────────────────────────────────────


def test_상세_구역_안의_큰_이미지는_남긴다():
    assert keep_image("temu", _image(2000), 1705, 3823) is None


@pytest.mark.parametrize(
    ("image", "reason"),
    [
        (_image(2000, width=200, height=200), "작음"),
        (_image(5000), "상세 구역 밖"),
        (_image(2000, alt="품목 사진 다른 상품"), "연관 상품"),
        (_image(2000, alt="item picture other product"), "연관 상품"),
        (_image(2000, src="https://aimg.kwcdn.com/upload_aimg/banner.png"), "배너·아바타"),
        (_image(2000, src="https://img.kwcdn.com/supplier-public-tag/x/avatar_300x300.jpeg"), "배너·아바타"),
    ],
    ids=["작은 썸네일", "구역 밖", "연관 상품 alt", "영문 연관 상품 alt", "배너 호스트", "판매자 아바타"],
)
def test_테무에서_상세_설명이_아닌_이미지는_이유와_함께_거른다(image: dict, reason: str):
    assert keep_image("temu", image, 1705, 3823) == reason


def test_알리에서_alt가_있는_480_정사각형은_연관_상품이다():
    related = _image(6000, width=480, height=480, alt="다른 상품 제목", src="https://ae-pic-a1.aliexpress-media.com/kf/S1.jpg_480x480q75.jpg_.avif")

    assert keep_image("aliexpress", related, 4980, 19306) == "연관 상품"


def test_알리에서_접힌_설명_구역_아래로_밀려난_원본_이미지는_구역_끝을_넘어도_남긴다():
    # "개요"가 접힌 채면 설명 이미지의 레이아웃 위치가 끝 표지("구매자 질문") 아래로 밀린다.
    # 설명 이미지는 썸네일 꼬리 없는 원본 주소이고 alt가 없어 구분할 수 있다.
    overflowed = _image(7177, width=2048, height=2048, src="https://ae-pic-a1.aliexpress-media.com/kf/S0044180b4a9eb8d5bf68fe2n.jpg")

    assert keep_image("aliexpress", overflowed, 3578, 5454) is None


def test_알리에서_구역_끝을_넘은_썸네일_주소_이미지는_여전히_거른다():
    category_tile = _image(6328, width=960, height=960, alt="식품과 식료품", src="https://ae-pic-a1.aliexpress-media.com/kf/S9.png_960x960.png_.avif")
    gallery_above = _image(505, width=1000, height=1000, src="https://ae-pic-a1.aliexpress-media.com/kf/Sgallery.jpg")

    assert keep_image("aliexpress", category_tile, 3578, 5454) == "상세 구역 밖"
    assert keep_image("aliexpress", gallery_above, 3578, 5454) == "상세 구역 밖"


def test_아직_안_불러온_lazy_이미지는_크기가_0이어도_남긴다():
    assert keep_image("temu", _image(2000, width=0, height=0, lazy=True), 1705, 3823) is None


def test_프레임에서_받은_이미지는_구역과_무관하게_크기만_본다():
    assert keep_image("aliexpress", _image(99999), 4980, 19306, is_frame=True) is None
    assert keep_image("aliexpress", _image(99999, width=100, height=100), 4980, 19306, is_frame=True) == "작음"


# ── 이미지 주소 정규화 ──────────────────────────────────────────────────────


def test_테무_이미지는_썸네일_옵션을_떼고_1600px_jpeg로_받는다():
    url = "https://img.kwcdn.com/product/fancy/abc.jpg?imageView2/2/w/800/q/70/format/avif"

    assert normalize_image_url("temu", url) == "https://img.kwcdn.com/product/fancy/abc.jpg?imageView2/2/w/1600/q/85"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://ae-pic-a1.aliexpress-media.com/kf/S1.jpg_480x480q75.jpg_.avif", "https://ae-pic-a1.aliexpress-media.com/kf/S1.jpg"),
        ("https://ae-pic-a1.aliexpress-media.com/kf/S2.png_960x960.png_.avif", "https://ae-pic-a1.aliexpress-media.com/kf/S2.png"),
        ("https://ae-pic-a1.aliexpress-media.com/kf/S3.jpg?width=1080&height=1234&hash=2314", "https://ae-pic-a1.aliexpress-media.com/kf/S3.jpg"),
    ],
    ids=["썸네일 꼬리", "png 썸네일 꼬리", "크기 질의"],
)
def test_알리_이미지는_썸네일_꼬리와_질의를_떼고_원본으로_받는다(url: str, expected: str):
    assert normalize_image_url("aliexpress", url) == expected


def test_모르는_사이트의_이미지_주소는_그대로_둔다():
    url = "https://cdn.example.com/a.jpg?x=1"

    assert normalize_image_url("other", url) == url


# ── 확장자 ────────────────────────────────────────────────────────────────


def test_확장자는_응답_content_type을_우선하고_없으면_경로를_본다():
    assert extension_of("https://x/a.jpg", "image/webp") == ".webp"
    assert extension_of("https://x/a.jpeg", None) == ".jpg"
    assert extension_of("https://x/a", None) == ".bin"


# ── 폴더 내보내기 ──────────────────────────────────────────────────────────


def _fake_fetch(responses: dict[str, tuple[bytes, str]]):
    calls: list[str] = []

    def fetch(url: str, referer: str) -> tuple[bytes, str | None]:
        calls.append(url)
        if url not in responses:
            raise OSError("404")
        return responses[url]

    fetch.calls = calls
    return fetch


def test_내보내기는_글을_사이트_주소_머리말과_함께_text_txt로_쓴다(tmp_path: Path):
    data = _listing("temu", text="제목\n본문")

    export_listing(data, [], tmp_path / "p", fetch=_fake_fetch({}))

    assert (tmp_path / "p" / "text.txt").read_text(encoding="utf-8") == "# temu https://temu.example/item/1\n제목\n본문"
    assert json.loads((tmp_path / "p" / "listing.json").read_text(encoding="utf-8"))["site"] == "temu"


def test_내보내기는_상세_구역_이미지만_순서대로_번호를_붙여_저장한다(tmp_path: Path):
    markers = [{"text": "제품 세부 정보", "top": 1705}, {"text": "관심 상품 둘러보기", "top": 3823}]
    images = [
        _image(2320, src="https://img.kwcdn.com/product/fancy/b.jpg?imageView2/2/w/800"),
        _image(160, src="https://img.kwcdn.com/product/fancy/gallery.jpg"),
        _image(1872, src="https://img.kwcdn.com/product/fancy/a.jpg?imageView2/2/w/800"),
        _image(3000, alt="품목 사진 다른 상품", src="https://img.kwcdn.com/product/fancy/other.jpg"),
    ]
    fetch = _fake_fetch({
        "https://img.kwcdn.com/product/fancy/a.jpg?imageView2/2/w/1600/q/85": (b"A", "image/jpeg"),
        "https://img.kwcdn.com/product/fancy/b.jpg?imageView2/2/w/1600/q/85": (b"B", "image/jpeg"),
    })

    summary = export_listing(_listing("temu", images=images, markers=markers), [], tmp_path / "p", fetch=fetch)

    assert (tmp_path / "p" / "img_01.jpg").read_bytes() == b"A"
    assert (tmp_path / "p" / "img_02.jpg").read_bytes() == b"B"
    assert not (tmp_path / "p" / "img_03.jpg").exists()
    assert summary["saved"] == 2
    assert summary["dropped"] == {"상세 구역 밖": 1, "연관 상품": 1}


def test_내보내기는_프레임_json의_이미지를_본문_이미지_뒤에_붙인다(tmp_path: Path):
    frame = _listing("aliexpress", images=[_image(10, src="https://ae-pic-a1.aliexpress-media.com/kf/F.jpg_480x480q75.jpg_.avif")])
    fetch = _fake_fetch({"https://ae-pic-a1.aliexpress-media.com/kf/F.jpg": (b"F", "image/jpeg")})

    summary = export_listing(_listing("aliexpress"), [frame], tmp_path / "p", fetch=fetch)

    assert (tmp_path / "p" / "img_01.jpg").read_bytes() == b"F"
    assert (tmp_path / "p" / "frame_01.json").exists()
    assert summary["saved"] == 1


def test_내보내기는_같은_원본_주소의_이미지를_한_번만_받는다(tmp_path: Path):
    images = [
        _image(2000, src="https://img.kwcdn.com/product/fancy/a.jpg?imageView2/2/w/800"),
        _image(2500, src="https://img.kwcdn.com/product/fancy/a.jpg?imageView2/2/w/500"),
    ]
    fetch = _fake_fetch({"https://img.kwcdn.com/product/fancy/a.jpg?imageView2/2/w/1600/q/85": (b"A", "image/jpeg")})

    summary = export_listing(_listing("temu", images=images), [], tmp_path / "p", fetch=fetch)

    assert fetch.calls == ["https://img.kwcdn.com/product/fancy/a.jpg?imageView2/2/w/1600/q/85"]
    assert summary["dropped"] == {"중복": 1}


def test_같은_폴더에_다시_내보내면_이전_이미지_파일을_지우고_새로_쓴다(tmp_path: Path):
    out = tmp_path / "p"
    out.mkdir()
    (out / "img_01.jpg").write_bytes(b"old1")
    (out / "img_02.jpg").write_bytes(b"old2")
    images = [_image(2000, src="https://img.kwcdn.com/product/fancy/a.jpg")]
    fetch = _fake_fetch({"https://img.kwcdn.com/product/fancy/a.jpg?imageView2/2/w/1600/q/85": (b"A", "image/jpeg")})

    export_listing(_listing("temu", images=images), [], out, fetch=fetch)

    assert (out / "img_01.jpg").read_bytes() == b"A"
    assert not (out / "img_02.jpg").exists()


def test_내보내기는_받기_실패한_이미지를_건너뛰고_실패_목록에_남긴다(tmp_path: Path):
    images = [_image(2000, src="https://img.kwcdn.com/product/fancy/gone.jpg")]

    summary = export_listing(_listing("temu", images=images), [], tmp_path / "p", fetch=_fake_fetch({}))

    assert summary["saved"] == 0
    assert len(summary["failures"]) == 1
    assert "gone.jpg" in summary["failures"][0]


def test_펼치기_전_글이_다르면_text_as_pasted_txt를_따로_쓴다(tmp_path: Path):
    data = _listing("aliexpress", text="펼친 글", text_as_pasted="접힌 글")

    export_listing(data, [], tmp_path / "p", fetch=_fake_fetch({}))

    assert (tmp_path / "p" / "text_as_pasted.txt").read_text(encoding="utf-8") == "# aliexpress https://aliexpress.example/item/1\n접힌 글"


def test_펼치기_전_글이_같으면_text_as_pasted_txt를_만들지_않는다(tmp_path: Path):
    data = _listing("temu", text="같은 글", text_as_pasted="같은 글")

    export_listing(data, [], tmp_path / "p", fetch=_fake_fetch({}))

    assert not (tmp_path / "p" / "text_as_pasted.txt").exists()


def test_shadow_dom_설명_글이_있으면_description_txt로_따로_쓴다(tmp_path: Path):
    data = _listing("aliexpress", detail_text="  " + "설명 글 " * 20)

    export_listing(data, [], tmp_path / "p", fetch=_fake_fetch({}))

    assert (tmp_path / "p" / "description.txt").read_text(encoding="utf-8") == ("설명 글 " * 20).strip()


def test_설명_글이_아주_짧으면_description_txt를_만들지_않는다(tmp_path: Path):
    # 번역 확장 같은 브라우저 위젯의 shadow DOM 글("설정빠른 번역몰입 번역")이 섞여 들어오는 경우
    data = _listing("temu", detail_text="설정빠른 번역몰입 번역")

    export_listing(data, [], tmp_path / "p", fetch=_fake_fetch({}))

    assert not (tmp_path / "p" / "description.txt").exists()


# ── 일괄 처리 ──────────────────────────────────────────────────────────────


def _write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_일괄_처리는_json을_시각_순서로_번호가_이어지는_폴더에_배정한다(tmp_path: Path):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    _write_json(downloads / "temu_2026-11-04T10-55-00.json", _listing("temu", collected_at="2026-11-04T10:55:00Z"))
    _write_json(downloads / "aliexpress_2026-11-04T10-48-00.json", _listing("aliexpress", collected_at="2026-11-04T10:48:00Z"))
    out_root = tmp_path / "_raw"
    (out_root / "strat_01").mkdir(parents=True)
    (out_root / "strat_02").mkdir()

    plan = plan_batch(downloads, out_root, prefix="strat")

    assert [(p.source.name, p.out_dir.name) for p in plan] == [
        ("aliexpress_2026-11-04T10-48-00.json", "strat_03"),
        ("temu_2026-11-04T10-55-00.json", "strat_04"),
    ]


def test_일괄_처리는_이미_내보낸_json을_건너뛴다(tmp_path: Path):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    done = _listing("temu", collected_at="2026-11-04T10:00:00Z")
    _write_json(downloads / "temu_2026-11-04T10-00-00.json", done)
    _write_json(downloads / "temu_2026-11-04T11-00-00.json", _listing("temu", collected_at="2026-11-04T11:00:00Z"))
    out_root = tmp_path / "_raw"
    (out_root / "strat_01").mkdir(parents=True)
    _write_json(out_root / "strat_01" / "listing.json", done)

    plan = plan_batch(downloads, out_root, prefix="strat")

    assert [(p.source.name, p.out_dir.name) for p in plan] == [("temu_2026-11-04T11-00-00.json", "strat_02")]


def test_일괄_처리는_수집_json이_아닌_파일을_무시한다(tmp_path: Path):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    _write_json(downloads / "other.json", {"foo": 1})
    (downloads / "temu_note.txt").write_text("x", encoding="utf-8")

    assert plan_batch(downloads, tmp_path / "_raw", prefix="strat") == []


# shadow DOM의 textContent에는 <style>·<script> 내용이 같이 딸려 온다 (알리 #product-description).
# 북마클릿도 고쳤지만, 이미 받은 JSON에도 남아 있어 저장 단계에서 한 번 더 걷어 낸다.
_CSS_BLOCK = ".product-description {\nposition: relative;\nmax-width: 944px;\n}\n.product-description span {\nmax-width: 100%;\n}\n"
_INLINE_CSS = "#detail_decorate_root .magic-0{margin-bottom:10px;overflow:hidden}#detail_decorate_root .magic-1{vertical-align:top}\n"
_SCRIPT = "window.adminAccountId=2670075647;\n"


def test_설명_글에서_css_규칙과_스크립트_줄을_걷어_낸다():
    clean_description = download_listing.clean_description

    text = _CSS_BLOCK + _INLINE_CSS + "1. IPX8 방수, 염수 분무 방지 구조\n운동 중에 떨어지지 않습니다.\n" + _SCRIPT

    assert clean_description(text) == "1. IPX8 방수, 염수 분무 방지 구조\n운동 중에 떨어지지 않습니다."


def test_설명_글의_중괄호가_상품_문구_안에_있으면_남긴다():
    clean_description = download_listing.clean_description

    assert clean_description("사이즈 {S, M, L} 중 선택\n세탁 시 주의: 30℃ 이하") == "사이즈 {S, M, L} 중 선택\n세탁 시 주의: 30℃ 이하"


def test_css만_있던_설명_글은_description_txt를_만들지_않는다(tmp_path: Path):
    data = _listing("aliexpress", detail_text=_CSS_BLOCK * 3 + _SCRIPT)

    export_listing(data, [], tmp_path / "p", fetch=_fake_fetch({}))

    assert not (tmp_path / "p" / "description.txt").exists()


def test_css가_섞인_설명_글은_걷어_낸_뒤_description_txt로_쓴다(tmp_path: Path):
    body = "골전도 기술을 채택한 오픈형 디자인은 편안한 착용을 보장합니다. " * 3
    data = _listing("aliexpress", detail_text=_CSS_BLOCK + body + "\n" + _SCRIPT)

    export_listing(data, [], tmp_path / "p", fetch=_fake_fetch({}))

    assert (tmp_path / "p" / "description.txt").read_text(encoding="utf-8") == body.strip()
