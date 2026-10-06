"""상세페이지 원문에서 판매자 구역만 남기는지 검증한다 (#253).

실제 쇼핑몰 원문은 저장소에 올리지 않으므로(tests/fixtures/README.md) 구역 순서만 흉내 낸
가짜 페이지(tests/conftest.py의 fixture)를 쓴다.
"""

import logging

from app.utils.seller_region import extract_seller_region

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


def test_쿠팡에서_분류_제목_옵션_필수표기만_남긴다(coupang_page):
    region = extract_seller_region(coupang_page)

    assert region.site == "coupang" and region.trimmed
    assert region.title == "접이식 원목 의자 3단 높이 조절"
    for kept in ("가구", "재질: 원목", "제조국(원산지)"):
        assert kept in region.text
    for removed in ("다른 상품 광고 문장", "로켓직구", "함께 본 상품"):
        assert removed not in region.text


def test_쇼핑몰은_알아봤지만_표지가_없으면_원문을_그대로_쓰고_경고한다(aliexpress_page, caplog):
    page = aliexpress_page.replace("상품 정보", "바뀐 화면 문구")

    with caplog.at_level(logging.WARNING):
        region = extract_seller_region(page)

    assert region.text == page and not region.trimmed and region.title is None
    assert region.site == "aliexpress"
    assert "aliexpress" in caplog.text


def test_쇼핑몰을_모르는_입력은_그대로_두고_경고하지_않는다(caplog):
    text = "접이식 원목 의자\n재료: 원목"

    with caplog.at_level(logging.WARNING):
        region = extract_seller_region(text)

    assert region.text == text and region.site is None and not region.trimmed
    assert caplog.text == ""
