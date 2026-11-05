"""상품 종류로 짐작해 채운 false, 원문에 부정 표기가 없는 false, 배터리·전원 모순 페이지의 확정을 None(모름)으로 되돌리는 후처리."""

import pytest

from app.agents.extraction import ExtractionAgent
from app.agents.extraction.guessed_flags import (
    drop_conflicted_battery,
    drop_conflicted_power,
    drop_guessed_false,
    drop_unsupported_false,
)
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


# --- 원문에 부정 표기가 없는 false (drop_unsupported_false) ---


@pytest.mark.parametrize("field", ["battery_included", "wireless_comm", "wireless_charging"])
@pytest.mark.parametrize("electrical", [True, None])
def test_전기_상품의_배터리_무선_false는_부정_표기가_없으면_모름으로_되돌린다(field, electrical):
    # 전기 상품은 배터리·무선 기능이 있을 수 있어, 언급이 없다는 것만으로 없다고 확정할 수 없다
    attributes = {field: False, "electrical_powered": electrical}

    assert drop_unsupported_false(attributes, "탁상 선풍기. 3단 풍량. 색상: 화이트") == [field]
    assert attributes[field] is None


@pytest.mark.parametrize("field, text", [
    ("battery_included", "배터리가 포함되어 있습니까?\n아니요"),
    ("battery_included", "배터리 미포함 (AA 건전지 별매)"),
    ("wireless_comm", "스마트 기기인가요? 아니요"),
    ("wireless_comm", "블루투스: 없음"),
    ("wireless_charging", "무선충전: 미지원"),
    ("wireless_charging", "Charging interface: Type-C"),
    ("wireless_charging", "충전 방법: 자기 충전. 충전 케이블 * 1"),
    ("battery_included", "1.7미터 길이의 코드, 정격 전압 220V"),
])
def test_페이지가_없다고_말한_false는_그대로_둔다(field, text):
    attributes = {field: False, "electrical_powered": True}

    assert drop_unsupported_false(attributes, text) == []
    assert attributes[field] is False


def test_전기를_쓰지_않는_상품의_배터리_무선_false는_그대로_둔다():
    # 재질·형태가 근거라 부정 표기가 없어도 false를 인정한다
    attributes = {"battery_included": False, "wireless_comm": False, "wireless_charging": False, "electrical_powered": False}

    assert drop_unsupported_false(attributes, "대나무 도마") == []
    assert all(attributes[f] is False for f in ("battery_included", "wireless_comm", "wireless_charging"))


def test_재질_표기가_없는_식물성_소재_false는_모름으로_되돌린다():
    attributes = {"plant_material": False}

    assert drop_unsupported_false(attributes, "페이셜 마사지 롤러. 색상: 핑크") == ["plant_material"]
    assert attributes["plant_material"] is None


@pytest.mark.parametrize("text", ["재질: 플라스틱", "Material: ABS+Metal", "스테인리스 스틸 본체", "재료: 폴리프로필렌",
                                  "PP소재", "재질: PC", "소재: 합성수지"])
def test_식물성이_아닌_재질이_적혀_있으면_plant_material_false를_인정한다(text):
    attributes = {"plant_material": False}

    assert drop_unsupported_false(attributes, text) == []
    assert attributes["plant_material"] is False


@pytest.mark.parametrize("text", ["인증정보: CE-Toy; CPC", "충전 단자: Type-C", "전용 앱(App)", "KC 적합성평가",
                                  "environment friendly"])
def test_재질이_아닌_단어_안의_약어·합성은_재질_표기로_보지_않는다(text):
    # CPC의 PC, Type의 pe, App의 pp, 적합성의 합성, environment의 iron
    attributes = {"plant_material": False}

    assert drop_unsupported_false(attributes, text) == ["plant_material"]


def test_이미지만_있는_입력은_글_근거가_없어_false를_모름으로_되돌린다():
    # 사진으로 짐작한 false는 믿지 않는다
    attributes = {"battery_included": False, "plant_material": False, "electrical_powered": True}

    assert drop_unsupported_false(attributes, "") == ["battery_included", "plant_material"]


def test_true와_다른_칸은_건드리지_않는다():
    attributes = {"battery_included": True, "wireless_comm": None, "medical_claim": False, "for_children": False,
                  "electrical_powered": True}

    assert drop_unsupported_false(attributes, "") == []
    assert (attributes["battery_included"], attributes["medical_claim"], attributes["for_children"]) == (True, False, False)


# --- 배터리 모순 (drop_conflicted_battery) ---

def test_배터리_모순이면_배터리_두_칸의_확정을_모름으로_되돌린다():
    attributes = {"battery_included": False, "battery_is_the_product": True, "electrical_powered": True}

    assert drop_conflicted_battery(attributes) == ["battery_included", "battery_is_the_product"]
    assert (attributes["battery_included"], attributes["battery_is_the_product"], attributes["electrical_powered"]) == (
        None, None, True)


def test_이미_모름인_배터리_칸은_바꾼_목록에_넣지_않는다():
    attributes = {"battery_included": None, "battery_is_the_product": None}

    assert drop_conflicted_battery(attributes) == []


def test_추출_결과에_근거_규칙이_적용된다(stub_model, records):
    # 전기 상품인데 부정 표기 없는 battery false, 재질 표기 없는 plant false → None. 부정 표기 있는 wireless_comm false는 유지
    reply = ProductAttributes(electrical_powered=True, battery_included=False, wireless_comm=False, plant_material=False)
    source = ExtractionInput(product_id="p-2", text_blocks=["USB 충전식 선풍기", "스마트 기기인가요? 아니요"])

    result = ExtractionAgent(stub_model(reply)).run(source)

    assert (result.battery_included, result.wireless_comm, result.plant_material) == (None, False, None)


def test_코드_규칙이_배터리_모순을_찾으면_배터리_칸을_확정하지_않는다(stub_model, records):
    reply = ProductAttributes(electrical_powered=True, battery_included=False, battery_is_the_product=True)
    source = ExtractionInput(product_id="p-3", text_blocks=["외장 배터리 케이스 1460mAh", "배터리 미포함"])

    result = ExtractionAgent(stub_model(reply)).run(source)

    assert (result.battery_included, result.battery_is_the_product) == (None, None)
    assert any("1460mAh" in conflict for conflict in result.conflicts)


# 소재 줄에 식물성 재질이 적혀 있는데 모델이 plant_material=false로 두면 '애매함'(None)으로 되돌리고 모순으로 남긴다
# (초안 50건 측정 2026-11-05: "72% Cotton", "소재: 종이"를 모델이 false로 둠). 코드는 true로 확정하지 않는다.
# 재질 줄 밖의 낱말("나무 심기", 포장 "종이 상자")은 근거가 아니다.
from app.agents.extraction.guessed_flags import drop_contradicted_plant_false


@pytest.mark.parametrize("text", [
    "소재 구성\n72% Cotton 25% Polyester 3% Spandex",
    "재료\n면,폴리에스테르,스판덱스",
    "소재: 종이",
    "본체재질\n원목",
    "Material\nBamboo",
    "성분\n100% 린넨",
])
def test_소재_줄의_식물성_재질과_어긋나는_plant_material_false는_모름으로_되돌린다(text):
    attributes = {"plant_material": False}

    dropped, conflicts = drop_contradicted_plant_false(attributes, text)

    assert dropped == ["plant_material"]
    assert attributes["plant_material"] is None
    assert len(conflicts) == 1


def test_식물성_모순_문장에는_소재_표기를_그대로_담는다():
    attributes = {"plant_material": False}

    _, conflicts = drop_contradicted_plant_false(attributes, "소재 구성\n72% Cotton 25% Polyester")

    assert conflicts == ['소재 표기 "72% Cotton 25% Polyester"에 식물성 재질이 있어 확인이 필요합니다.']


@pytest.mark.parametrize("value", [None, True])
def test_코드는_식물성_소재를_true로_확정하지_않고_모름이나_true는_그대로_둔다(value):
    attributes = {"plant_material": value}

    assert drop_contradicted_plant_false(attributes, "소재\n대나무") == ([], [])
    assert attributes["plant_material"] is value


@pytest.mark.parametrize("text", [
    "성분\n95% 폴리에스테르, 5% Nylon",
    "소재\n폴리에스테르 섬유\n충전식 휴대용 전기 핫팩 양면발열",
    "포장\n종이 상자\n재료\n플라스틱",
    "Temu의 나무 심기 프로그램\n재료\nABS",
    "소재\n면도기용 스테인리스",
])
def test_소재_줄에_식물성_재질이_없으면_false를_그대로_둔다(text):
    attributes = {"plant_material": False}

    assert drop_contradicted_plant_false(attributes, text) == ([], [])
    assert attributes["plant_material"] is False


def test_추출_결과에_식물성_false_되돌리기가_적용되고_모순으로_남는다(stub_model, records):
    reply = ProductAttributes(product_name="아기 양말", plant_material=False)
    agent = ExtractionAgent(stub_model(reply))

    result = agent.run(ExtractionInput(product_id="p", text_blocks=["소재 구성\n72% Cotton 25% Polyester 3% Spandex"]))

    assert result.plant_material is None
    assert any("72% Cotton" in c for c in result.conflicts)


# 스펙표가 "전자식: 아니요"인데 "전원 공급: 교류"처럼 전원 방식을 서로 다르게 적으면 electrical_powered를 확정하지 않는다
# (초안 50건 측정 2026-11-05: strat_16 캐비테이션 마사지기를 모델이 3회 모두 false로 둠. 실제는 교류 전원 제품)

@pytest.mark.parametrize("value", [True, False])
def test_전원_모순이면_electrical_powered_확정을_모름으로_되돌린다(value):
    attributes = {"electrical_powered": value, "heating": False}

    assert drop_conflicted_power(attributes) == ["electrical_powered"]
    assert (attributes["electrical_powered"], attributes["heating"]) == (None, False)


def test_이미_모름인_전원_칸은_바꾼_목록에_넣지_않는다():
    assert drop_conflicted_power({"electrical_powered": None}) == []


def test_코드_규칙이_전원_모순을_찾으면_전기_여부와_그에_기댄_false를_확정하지_않는다(stub_model, records):
    reply = ProductAttributes(electrical_powered=False, heating=False, battery_included=False)
    source = ExtractionInput(product_id="p-6", text_blocks=["초음파 바디 마사지기\n전자식\n아니요\n전원 공급\n교류"])

    result = ExtractionAgent(stub_model(reply)).run(source)

    assert result.electrical_powered is None
    # 전기 여부를 모르게 됐으므로 전기를 쓰지 않는다는 데 기댄 발열·배터리 false도 모름
    assert (result.heating, result.battery_included) == (None, None)
    assert any("전자식" in conflict and "교류" in conflict for conflict in result.conflicts)


def test_전원_모순이_없으면_electrical_powered를_그대로_둔다(stub_model, records):
    reply = ProductAttributes(electrical_powered=False)
    source = ExtractionInput(product_id="p-7", text_blocks=["발 지압 매트\n전자식\n아니요\n전원 공급\n전기 없음"])

    assert ExtractionAgent(stub_model(reply)).run(source).electrical_powered is False
