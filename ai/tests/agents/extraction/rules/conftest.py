"""실제 상세페이지 픽스처 회귀 테스트(test_fixtures.py)의 기대표.

픽스처는 상세페이지에서 규제 판정에 쓰이는 사실만 발췌한 축약본이다(tests/fixtures/README.md).
표기는 원문 그대로 보존한다 — 오탐은 대부분 표기 quirk에서 나오기 때문이다.
"""

import pytest

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


@pytest.fixture
def expected_rules() -> dict[str, tuple[set[tuple[str, str]], int]]:
    """픽스처 파일 이름 → (규칙이 뽑아야 하는 (항목, 값) 전부, 모순 후보 개수)."""
    return _EXPECTED
