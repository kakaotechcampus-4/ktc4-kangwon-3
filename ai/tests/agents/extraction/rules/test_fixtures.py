"""실제 상세페이지 픽스처로 규칙 레이어를 돌리는 회귀 테스트.

단위 테스트(test_attributes.py·test_voltage.py·test_battery_conflict.py)는 정규식을 짧은 합성 문자열로 검증한다.
그것만으로는 "실제 상세페이지에서 무엇을 잡고 무엇을 안 잡는지"를 알 수 없다.
실제로 "저전압(36V 이하)"를 "정격전압 36V"로 기록하던 오탐은 합성 문자열 테스트를
전부 통과한 상태에서 픽스처를 돌려보고 나서야 드러났다.

여기서는 LLM을 전혀 호출하지 않는다(규칙 레이어는 정규식뿐이라 API 키 없이 돈다).
LLM이 채우는 필드의 품질은 이 테스트의 범위가 아니다 — fixtures/_raw/의 원문으로
scripts/try_extraction.py를 돌려 수동 확인한다.

"""

from pathlib import Path

import pytest

from app.agents.extraction.agent import _merge_attributes
from app.agents.extraction.rules import (
    detect_battery_capacity_conflict,
    extract_rule_based_attributes,
)

FIXTURES_DIR = Path(__file__).parents[3] / "fixtures"

# 기대표는 conftest.py(expected_rules)
FIXTURE_NAMES = sorted(path.name for path in FIXTURES_DIR.glob("*.txt"))


def _rule_attributes(fixture_name: str) -> set[tuple[str, str]]:
    text = (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")
    # 같은 스펙이 페이지 안에서 여러 번 반복되므로(파워뱅크는 1460mAh가 9번 나온다)
    # 실제 Product에 담기는 형태와 같게 병합을 거친 뒤 비교한다.
    merged = _merge_attributes([], extract_rule_based_attributes([text]))
    return {(a.name, a.value) for a in merged}


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_픽스처에서_규칙이_뽑는_값이_고정된다(fixture_name: str, expected_rules):
    expected_attributes, _ = expected_rules[fixture_name]

    assert _rule_attributes(fixture_name) == expected_attributes


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_모순_후보는_파워뱅크_한_건에서만_발화한다(fixture_name: str, expected_rules):
    _, expected_conflicts = expected_rules[fixture_name]
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


def test_모든_텍스트_픽스처가_기대표에_들어_있다(expected_rules):
    # 픽스처를 새로 추가하고 기대값 등록을 잊으면 그 샘플은 아무도 안 돌려보게 된다.
    # (이미지 픽스처는 LLM이 있어야 읽을 수 있어 규칙 테스트 대상이 아니다.)
    assert set(FIXTURE_NAMES) == set(expected_rules)
