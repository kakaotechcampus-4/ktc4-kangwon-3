"""지원하는 쇼핑몰(AliExpress·Temu) 상세페이지에서 판매자 구역만 남기는지 검증한다 (#253).

실제 쇼핑몰 원문은 저장소에 올리지 않으므로(tests/fixtures/README.md) 구역 순서만 흉내 낸
가짜 페이지(tests/conftest.py의 fixture)를 쓴다.
"""

from app.agents.extraction.seller_region import extract_seller_region


def test_AliExpress에서_판매자_제목과_스펙만_남긴다(aliexpress_page):
    region = extract_seller_region(aliexpress_page)

    assert region.site == "aliexpress" and region.trimmed
    assert region.title == "접이식 원목 의자 3단 높이 조절"
    for kept in ("접이식 원목 의자 3단 높이 조절", "색상: 갈색", "재료: 원목", "판매자 설명 문장"):
        assert kept in region.text
    for removed in ("남아 있던 검색어", "허리 통증 완화", "5000mAh", "리뷰 문장", "질문 문장", "220V"):
        assert removed not in region.text


def test_Temu에서_리뷰와_구매_상자_안내를_뺀다(temu_page):
    region = extract_seller_region(temu_page)

    assert region.site == "temu" and region.trimmed
    assert region.title == "접이식 원목 의자 3단 높이 조절"
    assert "재료: 원목" in region.text
    for removed in ("리뷰 문장", "가게 이름", "가장 빠른 배송", "관세", "안전 결제"):
        assert removed not in region.text


def _with_purchase_box(temu_page: str, box: list[str]) -> str:
    return temu_page.replace("가장 빠른 배송: 5일", "\n".join(["가장 빠른 배송: 5일", "판매자", "8,290원", *box]))


def test_Temu_구매_상자의_수량과_배송_안내_사이에_있는_판매자_스펙은_남긴다(temu_page):
    # 국내 물류센터에서 보내는 판매자 화면 (kc_certified_fan)
    page = _with_purchase_box(temu_page, ["수량", "1", "배터리 용량(mAh)", "1200마", "이 판매자로부터 배송됩니다", "표준: 3,000원"])

    region = extract_seller_region(page)

    assert "배터리 용량(mAh)\n1200마" in region.text
    for removed in ("8,290원", "이 판매자로부터 배송됩니다", "표준: 3,000원"):
        assert removed not in region.text


def test_Temu_구매_상자에_수량_다음이_바로_배송_안내면_아무것도_더_남기지_않는다(temu_page):
    page = _with_purchase_box(temu_page, ["수량", "1", "해당 상품 무료 배송", "배송업체:"])

    assert extract_seller_region(page).text == extract_seller_region(temu_page).text


def test_Temu_구매_상자에_배송_안내가_없으면_스펙을_남기지_않는다(temu_page):
    # 끝을 모르면 구매 상자 나머지(가격 안내 등)까지 남길 수 있어 버린다
    page = _with_purchase_box(temu_page, ["수량", "1", "배터리 용량(mAh)", "1200마"])

    assert "1200마" not in extract_seller_region(page).text


def _without_full_title(temu_page: str) -> str:
    # 2026-11 화면: 경로 다음에 잘린 제목만 있고 전체 제목은 "가장 빠른 배송: 5일" 뒤에 붙어 나옴
    page = temu_page.replace("접이식 원목 의자 3단...\n접이식 원목 의자 3단 높이 조절\n", "접이식 원목 의자 3단...\n")
    return page.replace("가장 빠른 배송: 5일", "가장 빠른 배송: 5일접이식 원목 의자 3단 높이 조절")


def test_Temu_잘린_제목만_있으면_구매_상자_첫_줄에서_전체_제목을_찾는다(temu_page):
    region = extract_seller_region(_without_full_title(temu_page))

    assert region.title == "접이식 원목 의자 3단 높이 조절"
    assert "가장 빠른 배송" not in region.text


def test_Temu_잘린_제목의_전체_제목을_못_찾으면_잘린_제목을_쓴다(temu_page):
    page = _without_full_title(temu_page).replace("가장 빠른 배송: 5일접이식 원목 의자 3단 높이 조절", "가장 빠른 배송: 5일")

    assert extract_seller_region(page).title == "접이식 원목 의자 3단..."


def test_AliExpress에_구매자_질문과_면책_조항이_없어도_판매자_가게_앞에서_끊는다(aliexpress_page):
    page = "\n".join(
        line for line in aliexpress_page.splitlines()
        if not line.startswith(("구매자 질문", "질문 문장")) and line != "면책 조항"
    )
    page = page.replace("AliExpress의 약속", "판매자\n가게 이름\nAliExpress의 약속\n배송 안내 문장")

    region = extract_seller_region(page)

    assert region.trimmed and "판매자 설명 문장" in region.text
    for removed in ("가게 이름", "AliExpress의 약속", "배송 안내 문장"):
        assert removed not in region.text
