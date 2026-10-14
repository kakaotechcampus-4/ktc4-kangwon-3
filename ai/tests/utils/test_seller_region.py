"""상세페이지 원문에서 판매자 구역만 남기는지 검증한다 (#253).

실제 쇼핑몰 원문은 저장소에 올리지 않으므로(tests/fixtures/README.md) 구역 순서만 흉내 낸
가짜 페이지(tests/conftest.py의 fixture)를 쓴다.
"""

import logging

import pytest

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


def test_쿠팡은_소싱_출처가_아니라_지원하지_않고_원문을_그대로_둔다(coupang_page, caplog):
    # 쿠팡은 국내 판매처라 판매자가 상품을 떼오는 곳이 아니다(#257 리뷰)
    with caplog.at_level(logging.WARNING):
        region = extract_seller_region(coupang_page)

    assert region.text == coupang_page and region.site is None and not region.trimmed
    assert caplog.text == ""


@pytest.mark.parametrize("where", ["제목", "최근 검색어"])
def test_지원_밖_페이지에_Temu_글자가_있어도_Temu로_보지_않는다(coupang_page, where, caplog):
    # "Temu"가 든 줄로 알아보면 표지를 못 찾았다는 거짓 경고가 났다(#257 리뷰)
    line = "Temu 인기 접이식 원목 의자" if where == "제목" else "최근 검색어 Temu"
    page = coupang_page.replace("쿠팡 홈", f"{line}\n쿠팡 홈", 1)

    with caplog.at_level(logging.WARNING):
        region = extract_seller_region(page)

    assert region.site is None and not region.trimmed
    assert caplog.text == ""


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
