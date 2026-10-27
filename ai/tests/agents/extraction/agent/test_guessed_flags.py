"""상품 종류로 짐작해 채운 false를 None(모름)으로 되돌리는 후처리."""

import pytest

from app.agents.extraction import ExtractionAgent
from app.agents.extraction.guessed_flags import drop_guessed_false
from app.schemas.agent import ExtractionInput
from app.schemas.product import ProductAttributes


@pytest.mark.parametrize("field", ["food_contact", "skin_contact", "wireless_shield"])
def test_접촉_차단_칸의_false는_모름으로_되돌린다(field):
    # 이 칸의 false는 페이지가 "닿지 않는다"고 말할 때뿐이라 모델의 false는 짐작으로 본다
    attributes = {field: False}

    assert drop_guessed_false(attributes) == [field]
    assert attributes[field] is None


@pytest.mark.parametrize("field", ["food_contact", "skin_contact", "wireless_shield"])
def test_접촉_차단_칸의_true는_그대로_둔다(field):
    attributes = {field: True}

    assert drop_guessed_false(attributes) == []
    assert attributes[field] is True


@pytest.mark.parametrize("electrical", [True, None])
def test_전기_상품이거나_모르면_발열_false를_모름으로_되돌린다(electrical):
    attributes = {"heating": False, "electrical_powered": electrical}

    assert drop_guessed_false(attributes) == ["heating"]
    assert attributes["heating"] is None


def test_전기를_쓰지_않는_상품의_발열_false는_그대로_둔다():
    # 발열 false의 근거는 전기를 쓰지 않는 상품이라는 점
    attributes = {"heating": False, "electrical_powered": False}

    assert drop_guessed_false(attributes) == []
    assert attributes["heating"] is False


def test_다른_칸의_false는_건드리지_않는다():
    attributes = {"medical_claim": False, "for_children": False, "plant_material": False, "wireless_comm": False}

    assert drop_guessed_false(attributes) == []
    assert all(value is False for value in attributes.values())


def test_추출_결과에_후처리가_적용된다(stub_model, records):
    reply = ProductAttributes(food_contact=False, heating=False, electrical_powered=True, medical_claim=False)

    result = ExtractionAgent(stub_model(reply)).run(ExtractionInput(product_id="p-1", text_blocks=["LED 스탠드 조명"]))

    assert (result.food_contact, result.heating, result.medical_claim) == (None, None, False)
