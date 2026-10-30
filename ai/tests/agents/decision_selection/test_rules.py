"""판단 선택 코드 규칙: 통관 항상 선택, true 필드 선택, 전기 제품 무선 정보 없음(원칙 2)."""

import pytest

from app.agents.decision_selection.rules import TRUE_FIELDS, rule_reasons
from app.schemas.product import Product
from app.schemas.schemas import ToolName


def _product(**fields) -> Product:
    return Product(product_id="rule-001", source_url=None, **fields)


def test_정보가_없으면_통관만_선택된다():
    assert set(rule_reasons(_product())) == {ToolName.CUSTOMS}


@pytest.mark.parametrize(("tool", "field"), [(tool, field) for tool, fields in TRUE_FIELDS.items() for field in fields])
def test_true_필드_하나로_해당_Tool이_선택된다(tool, field):
    reasons = rule_reasons(_product(**{field: True}))

    assert f"{field}=true" in reasons[tool]


def test_걸린_필드를_모두_근거로_남긴다():
    reasons = rule_reasons(_product(food_contact=True, cosmetic_claim=True))

    assert reasons[ToolName.FOOD_DRUG] == ["food_contact=true", "cosmetic_claim=true"]


def test_false_필드는_선택하지_않는다():
    fields = {field: False for fields in TRUE_FIELDS.values() for field in fields}

    assert set(rule_reasons(_product(**fields))) == {ToolName.CUSTOMS}


def test_전기_제품인데_무선_정보가_없으면_전파를_선택한다():
    reasons = rule_reasons(_product(battery_included=True, wireless_comm=False, wireless_charging=False))

    assert reasons[ToolName.RADIO] == [
        "battery_included=true인데 wireless_shield=None (전기 제품의 무선 기능 정보 없음)",
    ]


def test_전기_제품이어도_무선_필드가_모두_false면_전파를_선택하지_않는다():
    product = _product(electrical_powered=True, wireless_comm=False, wireless_charging=False, wireless_shield=False)

    assert ToolName.RADIO not in rule_reasons(product)


def test_무선_필드가_true면_정보_없음_규칙은_덧붙이지_않는다():
    reasons = rule_reasons(_product(electrical_powered=True, wireless_comm=True))

    assert reasons[ToolName.RADIO] == ["wireless_comm=true"]


def test_전기_제품이_아니면_무선_정보가_없어도_전파를_선택하지_않는다():
    assert ToolName.RADIO not in rule_reasons(_product(electrical_powered=None))
