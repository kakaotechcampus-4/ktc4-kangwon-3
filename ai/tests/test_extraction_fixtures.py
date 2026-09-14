"""실제 상세페이지 픽스처로 규칙 레이어를 돌리는 회귀 테스트.

단위 테스트(test_extraction_rules.py)는 정규식을 짧은 합성 문자열로 검증한다.
그것만으로는 "실제 상세페이지에서 무엇을 잡고 무엇을 안 잡는지"를 알 수 없다.
실제로 "저전압(36V 이하)"를 "정격전압 36V"로 기록하던 오탐은 합성 문자열 테스트를
전부 통과한 상태에서 픽스처를 돌려보고 나서야 드러났다.

여기서는 LLM을 전혀 호출하지 않는다(규칙 레이어는 정규식뿐이라 API 키 없이 돈다).
LLM이 채우는 필드의 품질은 이 테스트의 범위가 아니다 — fixtures/_raw/의 원문으로
scripts/try_extraction.py를 돌려 수동 확인한다.

픽스처는 상세페이지에서 규제 판정에 쓰이는 사실만 발췌한 축약본이다(fixtures/README.md).
표기는 원문 그대로 보존한다 — 오탐은 대부분 표기 quirk에서 나오기 때문이다.
"""

from pathlib import Path

import pytest

from app.agents.extraction import _merge_attributes
from app.utils.extraction_rules import (
    detect_battery_capacity_conflict,
    extract_rule_based_attributes,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# 픽스처별로 규칙 레이어가 뽑아야 하는 (항목, 값) 전부와 모순 후보 개수.
# 값은 원문 표기 그대로여야 한다(대소문자·한정어 포함).
_EXPECTED: dict[str, tuple[set[tuple[str, str]], int]] = {
    "age_label_vs_target_mismatch.txt": (
        {("인증정보", "CE-Toy"), ("인증정보", "CPC")},
        0,
    ),
    "ali_sample.txt": (
        {("인증정보", "CE-RoHS"), ("인증정보", "CE-EMC")},
        0,
    ),
    # 화학·재질·발열·식물성 소재는 정규식으로 확정할 수 있는 패턴이 아니라 전부 LLM 몫이다.
    # 규칙이 아무것도 안 잡는 게 정상이며, 여기서 뭔가 잡히기 시작하면 오탐을 의심해야 한다.
    "chemical_product_diffuser.txt": (set(), 0),
    "chinese_material_labels.txt": (set(), 0),
    "heating_device_no_claim.txt": (set(), 0),
    "plant_material_basket.txt": (set(), 0),
    "wireless_shield_rfid.txt": (set(), 0),
    # 제목엔 "1460mAh 케이스", 스펙표엔 "배터리 미포함" — 규칙이 잡아야 하는 유일한 모순 후보.
    "power_bank.txt": (
        {("배터리 용량", "1460mAh")},
        1,
    ),
    # "저전압(36V 이하)"는 정격이 36V라는 뜻이 아니다. 한정어가 값에 남아 있어야 한다.
    "toy_weapon_shaped.txt": (
        {
            ("인증정보", "CE-Toy"),
            ("인증정보", "CE-RoHS"),
            ("인증정보", "CE-EMC"),
            ("인증정보", "CPC"),
            ("정격전압", "36V 이하"),
        },
        0,
    ),
    # 스펙표의 "작동 전압 ≤36V"도 마찬가지로 상한 표기다.
    "wireless_charging_pad.txt": (
        {
            ("인증정보", "CE-RED"),
            ("인증정보", "CE-RoHS"),
            ("인증정보", "CE-EMC"),
            ("정격전압", "≤36V"),
        },
        0,
    ),
    # 인증번호 두 종류가 실제로 적힌 유일한 샘플(Temu 핸디선풍기).
    # 두 패턴은 이 픽스처 전까지 합성 문자열로만 검증돼 있었다.
    "kc_certified_fan.txt": (
        {
            ("KC 인증번호", "XU101030-17003A"),
            ("전파 인증번호", "R-R-PO7-FX-028"),
            ("인증정보", "KC"),
        },
        0,
    ),
}


def _rule_attributes(fixture_name: str) -> set[tuple[str, str]]:
    text = (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")
    # 같은 스펙이 페이지 안에서 여러 번 반복되므로(파워뱅크는 1460mAh가 9번 나온다)
    # 실제 Product에 담기는 형태와 같게 병합을 거친 뒤 비교한다.
    merged = _merge_attributes([], extract_rule_based_attributes([text]))
    return {(a.name, a.value) for a in merged}


@pytest.mark.parametrize("fixture_name", sorted(_EXPECTED))
def test_픽스처에서_규칙이_뽑는_값이_고정된다(fixture_name: str):
    expected_attributes, _ = _EXPECTED[fixture_name]

    assert _rule_attributes(fixture_name) == expected_attributes


@pytest.mark.parametrize("fixture_name", sorted(_EXPECTED))
def test_모순_후보는_파워뱅크_한_건에서만_발화한다(fixture_name: str):
    _, expected_conflicts = _EXPECTED[fixture_name]
    text = (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")

    assert len(detect_battery_capacity_conflict([text])) == expected_conflicts


def test_전압_상한_표기가_정격으로_둔갑하지_않는다():
    # 전안법은 직류 30V 초과를 기준으로 삼는다. "36V 이하"인 제품은 30V 이하일 수도 있어
    # 아직 확정할 수 없으므로, 한정어를 뗀 "36V"로 넘기면 하위 판정이 틀어진다.
    upper_bounds = {
        value
        for name, value in _rule_attributes("toy_weapon_shaped.txt")
        | _rule_attributes("wireless_charging_pad.txt")
        if name == "정격전압"
    }

    assert upper_bounds == {"36V 이하", "≤36V"}
    assert "36V" not in upper_bounds


def test_인증번호_패턴이_실제_상세페이지에서_동작한다():
    # 한 줄에 두 종류가 나란히 적힌 실제 표기:
    #   "KC 방송통신기자재등 적합성평가: R-R-PO7-FX-028; KC 안전확인 (전기용품): XU101030-17003A"
    # 두 패턴은 이 샘플을 구하기 전까지 합성 문자열로만 검증돼 있어서, 자릿수 범위가
    # 실물과 맞는지 확인된 적이 없었다. 발급 시기에 따라 자릿수가 달라지므로
    # 형식이 다른 샘플이 생기면 여기에 함께 추가한다.
    found = _rule_attributes("kc_certified_fan.txt")

    assert ("KC 인증번호", "XU101030-17003A") in found  # 접미 영문자까지 포함
    assert ("전파 인증번호", "R-R-PO7-FX-028") in found  # 하이픈 4개짜리 신형 표기


def test_모든_텍스트_픽스처가_기대표에_들어_있다():
    # 픽스처를 새로 추가하고 기대값 등록을 잊으면 그 샘플은 아무도 안 돌려보게 된다.
    # (이미지 픽스처는 LLM이 있어야 읽을 수 있어 규칙 테스트 대상이 아니다.)
    actual = {path.name for path in FIXTURES_DIR.glob("*.txt")}

    assert actual == set(_EXPECTED)
