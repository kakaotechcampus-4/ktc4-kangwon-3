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


def test_전압_한정어가_값에_함께_보존된다():
    # "36V 이하"는 정격이 36V라는 뜻이 아니라 상한이 36V라는 뜻이다. 한정어를 떼고
    # "정격전압 36V"로 넘기면 하위 판정(전안법의 직류 30V 초과 기준)이 틀어진다.
    text_blocks = ["저전압(36V 이하) 어린이용", "작동 전압 ≤36V", "최대 12V 출력", "입력 5V 이상"]

    voltages = [a.value for a in extract_rule_based_attributes(text_blocks) if a.name == "정격전압"]

    assert voltages == ["36V 이하", "≤36V", "최대 12V", "5V 이상"]


def test_하한_한정어도_상한과_똑같이_보존된다():
    # 상한만 처리하면 "최소 5V"가 "정격전압 5V"로 둔갑해서, 실제로는 220V인 제품이
    # 저전압으로 넘어간다. 상한·하한을 대칭으로 다뤄야 한다.
    text_blocks = ["≥36V", ">36V", "최소 5V", "12V 이내", "12V max"]

    voltages = [a.value for a in extract_rule_based_attributes(text_blocks) if a.name == "정격전압"]

    assert voltages == ["≥36V", ">36V", "최소 5V", "12V 이내", "12V max"]


def test_공차_표기는_정격전압으로_잡지_않는다():
    # "DC 5V±0.5V"에서 0.5V는 정격이 아니라 공차다. 앞자리를 건너뛴 "5V"가 새로
    # 생기지도 않아야 한다(원문에 없던 전압을 만들어내면 안 된다).
    voltages = [
        a.value for a in extract_rule_based_attributes(["DC 5V±0.5V", "5V +0.2V"]) if a.name == "정격전압"
    ]

    assert voltages == ["5V", "5V"]


def test_한정어가_없는_전압은_그대로_뽑는다():
    text_blocks = ["정격전압 220V", "220V정격", "AC-220V-A1 모델"]

    voltages = [a.value for a in extract_rule_based_attributes(text_blocks) if a.name == "정격전압"]

    assert voltages == ["220V", "220V", "220V"]


def test_범위_표기는_양쪽_값으로_쪼개진다():
    # 정규식은 범위를 하나의 개념으로 이해하지 못한다. "3.7V~4.2V"는 두 항목이 되며,
    # 뒤쪽은 "~4.2V"로 남아 상한이라는 것만 전달된다. 범위 해석은 LLM 몫이다.
    voltages = [
        a.value for a in extract_rule_based_attributes(["DC 3.7V~4.2V 충전"]) if a.name == "정격전압"
    ]

    assert voltages == ["3.7V", "~4.2V"]


def test_패턴이_없으면_빈_리스트를_반환한다():
    assert extract_rule_based_attributes(["그냥 평범한 설명 문구입니다."]) == []
    assert detect_battery_capacity_conflict(["그냥 평범한 설명 문구입니다."]) == []


def test_용량_표기와_배터리_미포함_문구가_같이_있으면_모순_후보로_잡는다():
    # Given: 실제 테스트 중 발견한 파워뱅크 케이스와 동일한 패턴
    text_blocks = [
        "9482 블랙 블록 아이폰 MagSafe 외장 배터리 케이스 MagSafe 1460mAh 케이스",
        "배터리 속성 배터리 미포함",
    ]

    conflicts = detect_battery_capacity_conflict(text_blocks)

    assert len(conflicts) == 1
    assert "1460mAh" in conflicts[0]
    # 확정이 아니라 검토가 필요한 후보로 전달한다(리뷰 반영).
    assert "모순 가능성" in conflicts[0]


def test_용량_표기만_있고_미포함_문구가_없으면_모순이_아니다():
    text_blocks = ["보조배터리 10000mAh 대용량"]

    assert detect_battery_capacity_conflict(text_blocks) == []


def test_부속품_배터리_미포함은_모순으로_보지_않는다():
    # 본체 내장 배터리 용량과 별개로 리모컨용 배터리가 미포함인 것은 모순이 아니다.
    text_blocks = ["드론 내장 배터리 1500mAh", "리모컨용 AA 배터리 미포함"]

    assert detect_battery_capacity_conflict(text_blocks) == []


def test_부속품_문구가_있어도_본체_배터리_미포함이_따로_있으면_모순_후보다():
    text_blocks = [
        "MagSafe 1460mAh 케이스",
        "리모컨용 AA 배터리 미포함",
        "배터리 속성 배터리 미포함",
    ]

    conflicts = detect_battery_capacity_conflict(text_blocks)

    assert len(conflicts) == 1
