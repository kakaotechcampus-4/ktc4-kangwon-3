"""에이전트의 판매자 영역 적용: 쇼핑몰 글 제외, 판매자 제목 보존 (#251, #253)."""

from app.agents.extraction import ExtractionAgent
from app.schemas.agent import ExtractionInput
from app.schemas.product import ProductAttributes

_TITLE = "접이식 원목 의자 3단 높이 조절"


def test_쇼핑몰이_붙인_글은_모델과_규칙에_넘기지_않는다(stub_model, records, aliexpress_page):
    # 판매자는 배터리 미포함, 연관 상품에만 5000mAh (#251 가짜 모순 구조)
    model = stub_model(ProductAttributes(product_name="접이식 원목 의자"))

    result = ExtractionAgent(model).run(ExtractionInput(product_id="prod-region", text_blocks=[aliexpress_page]))

    sent = "\n".join(part["text"] for part in model.received[0][1].content if part.get("type") == "text")
    assert "재료: 원목" in sent
    for removed in ("남아 있던 검색어", "허리 통증 완화", "5000mAh", "리뷰 문장"):
        assert removed not in sent
    assert result.conflicts == []
    assert not any("5000mAh" in a.value for a in result.attributes)


def test_모델이_빠뜨린_판매자_제목은_listing_text_맨_앞에_원문으로_넣는다(stub_model, records, aliexpress_page):
    model = stub_model(ProductAttributes(listing_text=["판매자 설명 문장"]))

    result = ExtractionAgent(model).run(ExtractionInput(product_id="prod-title", text_blocks=[aliexpress_page]))

    assert result.listing_text == [_TITLE, "판매자 설명 문장"]


def test_판매자_제목이_이미_있으면_다시_넣지_않는다(stub_model, records, aliexpress_page):
    model = stub_model(ProductAttributes(listing_text=[_TITLE, "판매자 설명 문장"]))

    result = ExtractionAgent(model).run(ExtractionInput(product_id="prod-title-2", text_blocks=[aliexpress_page]))

    assert result.listing_text == [_TITLE, "판매자 설명 문장"]


def test_여러_블록에_같은_판매자_제목이_있어도_한_번만_넣는다(stub_model, records, aliexpress_page):
    # 같은 페이지를 두 번 수집하는 등 블록마다 제목이 반복되는 경우
    model = stub_model(ProductAttributes(listing_text=["판매자 설명 문장"]))

    result = ExtractionAgent(model).run(
        ExtractionInput(product_id="prod-title-3", text_blocks=[aliexpress_page, aliexpress_page])
    )

    assert result.listing_text == [_TITLE, "판매자 설명 문장"]
