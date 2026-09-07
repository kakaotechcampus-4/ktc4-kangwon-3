"""extraction_rules.py 단위 테스트. LLM을 전혀 안 써서 API 키 없이도 돈다."""

from app.utils.extraction_rules import (
    detect_battery_capacity_conflict,
    extract_rule_based_attributes,
)


def test_인증코드와_전압과_용량과_주파수를_각각_뽑는다():
    text_blocks = ["인증정보: CE-RoHS; CE-EMC(Electric)", "작동 전압 220V", "1460mAh", "2.4GHz 무선 조종"]

    attributes = extract_rule_based_attributes(text_blocks)

    names_and_values = {(a.name, a.value) for a in attributes}
    assert ("인증정보", "CE-RoHS") in names_and_values
    assert ("인증정보", "CE-EMC") in names_and_values
    assert ("정격전압", "220V") in names_and_values
    assert ("배터리 용량", "1460mAh") in names_and_values
    assert ("통신 주파수", "2.4GHz") in names_and_values


def test_한글이_바로_붙은_표기도_뽑는다():
    # 한국어 페이지에서 흔한 "CE인증", "KC인증번호", "220V정격" 같은 붙여쓰기.
    attributes = extract_rule_based_attributes(["CE인증 획득, KC인증번호 표기, 220V정격, 1460mAh케이스"])

    values = {a.value for a in attributes}
    assert {"CE", "KC", "220V", "1460mAh"} <= values


def test_영단어_안의_우연한_일치는_인증마크로_보지_않는다():
    # PRICE의 "CE", BLACK의 "KC" 같은 것은 인증 마크가 아니다.
    attributes = extract_rule_based_attributes(["PRICE BLACK EDITION"])

    assert [a for a in attributes if a.name == "인증정보"] == []


def test_KC_안전인증번호와_전파_인증번호를_뽑는다():
    text_blocks = [
        "안전인증번호 XU101234-19001 / 어린이제품 CB061R0069-3002",
        "적합성평가번호 R-R-abc-DEF123, 구형 표기 KCC-REM-MJT-MJT",
    ]

    attributes = extract_rule_based_attributes(text_blocks)

    kc_numbers = {a.value for a in attributes if a.name == "KC 인증번호"}
    radio_numbers = {a.value for a in attributes if a.name == "전파 인증번호"}
    assert kc_numbers == {"XU101234-19001", "CB061R0069-3002"}
    assert radio_numbers == {"R-R-abc-DEF123", "KCC-REM-MJT-MJT"}


def test_패턴이_없으면_빈_리스트를_반환한다():
    assert extract_rule_based_attributes(["그냥 평범한 설명 문구입니다."]) == []
    assert detect_battery_capacity_conflict(["그냥 평범한 설명 문구입니다."]) == []


def test_용량_표기와_배터리_미포함_문구가_같이_있으면_모순으로_잡는다():
    # Given: 실제 테스트 중 발견한 파워뱅크 케이스와 동일한 패턴
    text_blocks = [
        "9482 블랙 블록 아이폰 MagSafe 외장 배터리 케이스 MagSafe 1460mAh 케이스",
        "배터리 속성 배터리 미포함",
    ]

    conflicts = detect_battery_capacity_conflict(text_blocks)

    assert len(conflicts) == 1
    assert "1460mAh" in conflicts[0]


def test_용량_표기만_있고_미포함_문구가_없으면_모순이_아니다():
    text_blocks = ["보조배터리 10000mAh 대용량"]

    assert detect_battery_capacity_conflict(text_blocks) == []
