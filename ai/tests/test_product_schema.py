"""상품 스키마가 들어오는 값을 어떻게 정리하는지 검증한다. LLM을 부르지 않는다."""

import pytest

from app.schemas.product import Product, ProductAttributes


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n"])
def test_빈_텍스트는_None으로_정리된다(blank):
    # 모델이 "값 없음"을 None 대신 ""로 주면 하위 단계가 "값이 있다"로 오해한다.
    # 예를 들어 target_age가 ""인데 연령 표기가 있는 것처럼 처리된다.
    product = ProductAttributes(
        product_name=blank, category=blank, intended_use=blank, target_age=blank
    )

    assert product.product_name is None
    assert product.category is None
    assert product.intended_use is None
    assert product.target_age is None


def test_실제_값은_그대로_남는다():
    product = ProductAttributes(product_name="4채널 드론", target_age="만 14세 이상")

    assert product.product_name == "4채널 드론"
    # 원문 보존이 요구사항이라 앞뒤 공백 외에는 손대지 않는다.
    assert product.target_age == "만 14세 이상"


def test_Product도_같은_정리를_물려받는다():
    product = Product(product_id="p1", target_age="")

    assert product.target_age is None
