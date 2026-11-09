"""판단 선택 코드 규칙: 통관 항상 선택, true 필드 선택, 전기 제품 무선 정보 없음(원칙 2), 모순(원칙 6)."""

import pytest

from app.agents.decision_selection.rules import TRUE_FIELDS, rule_reasons
from app.schemas.product import Product
from app.schemas.schemas import ToolName


def _product(**fields) -> Product:
    return Product(product_id="rule-001", source_url=None, **({"product_name": "상품"} | fields))


def test_상품명만_있고_필드가_비면_통관만_선택된다():
    assert set(rule_reasons(_product())) == {ToolName.CUSTOMS}


def test_어떤_상품인지_모르면_관련_필드가_전부_None인_Tool을_모두_선택한다():
    reasons = rule_reasons(_product(product_name=None))

    assert set(reasons) == set(TRUE_FIELDS) | {ToolName.CUSTOMS}
    assert reasons[ToolName.CHILDREN] == [
        "product_name·category·intended_use·for_children=None (어떤 상품인지 몰라 정보 부족)"
    ]


def test_어떤_상품인지_몰라도_관련_필드에_값이_있는_Tool은_이_규칙으로_고르지_않는다():
    reasons = rule_reasons(_product(product_name=None, for_children=False))

    assert ToolName.CHILDREN not in reasons


@pytest.mark.parametrize("field", ["product_name", "category", "intended_use"])
def test_상품명_종류_용도_중_하나라도_있으면_이_규칙을_걸지_않는다(field):
    reasons = rule_reasons(_product(**({"product_name": None} | {field: "선풍기"})))

    assert set(reasons) == {ToolName.CUSTOMS}


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
    reasons = rule_reasons(_product(battery_included=True, wireless_comm=False))

    assert reasons[ToolName.RADIO] == [
        "battery_included=true인데 wireless_charging=None (전기 제품의 무선 기능 정보 없음)",
    ]


def test_전기_제품이어도_통신_무선충전이_false면_전파를_선택하지_않는다():
    product = _product(electrical_powered=True, wireless_comm=False, wireless_charging=False)

    assert ToolName.RADIO not in rule_reasons(product)


def test_무선_필드가_true면_정보_없음_규칙은_덧붙이지_않는다():
    reasons = rule_reasons(_product(electrical_powered=True, wireless_comm=True))

    assert reasons[ToolName.RADIO] == ["wireless_comm=true"]


def test_전기_제품이_아니면_무선_정보가_없어도_전파를_선택하지_않는다():
    assert ToolName.RADIO not in rule_reasons(_product(electrical_powered=None))


def test_분야_말이_든_모순이면_그_분야_관련_필드가_전부_None인_Tool만_선택한다():
    # 배터리 용량 표기와 "배터리 미포함"이 충돌해 전기 필드를 비운 보조배터리 케이스. 다른 분야 필드도 None
    product = _product(conflicts=["1460mAh 표기와 '배터리 미포함'이 함께 있음"])

    reasons = rule_reasons(product)

    assert set(reasons) == {ToolName.CUSTOMS, ToolName.ELECTRICAL}
    assert reasons[ToolName.ELECTRICAL] == [
        "conflicts에 '배터리' 모순, electrical_powered·battery_included·battery_is_the_product·heating=None "
        "(상품 정보 모순으로 정보 부족)"
    ]


@pytest.mark.parametrize("conflict", [
    "제목은 \"봄/여름\"인데 스펙표 계절은 \"봄/가을\"입니다.",
    "제목은 \"남성용\"인데 스펙표 대상 고객은 \"남녀공용-성인\"입니다.",
])
def test_분야_말이_없는_모순은_모순_규칙을_걸지_않는다(conflict):
    assert set(rule_reasons(_product(conflicts=[conflict]))) == {ToolName.CUSTOMS}


@pytest.mark.parametrize(("conflict", "tool"), [
    ("제목 안에 \"4255mWh\"와 \"4225mWh\"가 함께 있습니다.", ToolName.ELECTRICAL),
    ("판매자 문구 \"가려움 완화\"가 효능 표방일 수 있습니다.", ToolName.FOOD_DRUG),
    ("제목은 \"0-2 세\"인데 스펙표 연령대는 \"1~3세\"입니다.", ToolName.CHILDREN),
    ("제목은 Bluetooth 5.3인데 스펙표는 유선입니다.", ToolName.RADIO),
])
def test_모순_문장의_분야_말로_관련_Tool을_고른다(conflict, tool):
    assert set(rule_reasons(_product(conflicts=[conflict]))) == {ToolName.CUSTOMS, tool}


def test_모순이_있어도_관련_필드에_값이_있으면_모순_규칙은_걸지_않는다():
    product = _product(conflicts=["배터리 표기 충돌"], electrical_powered=False, battery_included=True)

    reasons = rule_reasons(product)

    assert reasons[ToolName.ELECTRICAL] == ["battery_included=true"]


def test_모순이_없으면_필드가_None이어도_모순_규칙은_걸지_않는다():
    assert set(rule_reasons(_product())) == {ToolName.CUSTOMS}
