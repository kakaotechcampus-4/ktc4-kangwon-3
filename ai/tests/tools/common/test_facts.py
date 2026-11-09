"""모델이 뽑은 조건의 원문 대조. 다듬어 적은 값은 받고, 지정한 조각에 없는 인용과 인용에 없는 값은 막는다."""

from dataclasses import dataclass

import pytest

from app.tools.common.facts import quote_matches

SNIPPETS = {
    "listing-0": "USB 탁상용 미니 선풍기",
    "listing-1": "5W USB Desk Fan with CE RoHS Certificates",
    "listing-2": "Features | 1.Input : DC5V- 1A",
    "listing-3": "Customization | Yes",
}


@dataclass
class Fact:
    value: str
    evidence_id: str
    quote: str
    field: str = "product_type"


@pytest.mark.parametrize("fact", [
    Fact("USB 탁상용 미니 선풍기", "listing-0", "USB 탁상용 미니 선풍기"),  # 그대로
    Fact("탁상용 선풍기", "listing-0", "탁상용 미니 선풍기"),  # 가운데 낱말 생략 (재현 사례)
    Fact("Desk fan", "listing-1", "5W USB Desk Fan with CE RoHS Certificates"),  # 대소문자 (재현 사례)
    Fact("DC 5V", "listing-2", "Input : DC5V- 1A"),  # 공백 차이
    Fact("ＤＣ５Ｖ", "listing-2", "DC5V"),  # 전각 문자
], ids=["그대로", "낱말_생략", "대소문자", "공백", "전각"])
def test_다듬어_적은_값은_받는다(fact):
    assert quote_matches(fact, SNIPPETS)


@pytest.mark.parametrize("fact", [
    Fact("선풍기", "listing-0", "USB 탁상용 선풍기"),  # 인용이 원문에 이어서 있지 않음
    Fact("유리", "listing-0", "유리 주전자"),  # 원문 어디에도 없는 인용
    Fact("5V", "listing-3", "DC5V"),  # 다른 조각에 있는 인용 (조각 ID까지 맞아야 함)
    Fact("5V", "missing", "DC5V"),  # 없는 조각 ID
    Fact("스탠드 선풍기", "listing-0", "USB 탁상용 미니 선풍기"),  # 인용에 없는 낱말
    Fact("선풍기 탁상용", "listing-0", "USB 탁상용 미니 선풍기"),  # 낱말 순서가 뒤집힘
    Fact("", "listing-0", "USB 탁상용 미니 선풍기"),  # 빈 값
    Fact("선풍기", "listing-0", "   "),  # 빈 인용
], ids=["이어지지_않은_인용", "원문에_없는_인용", "다른_조각", "없는_조각_ID", "없는_낱말", "순서_뒤집힘", "빈_값",
        "빈_인용"])
def test_지정한_조각에_없는_인용이나_인용에_없는_값은_막는다(fact):
    assert not quote_matches(fact, SNIPPETS)


def test_판단_칸은_값을_보지_않고_인용만_본다():
    judged = Fact("예", "listing-2", "DC5V", field="battery_only")

    assert quote_matches(judged, SNIPPETS, value_in_quote=False)
    assert not quote_matches(Fact("예", "listing-2", "AC220V", field="battery_only"), SNIPPETS, value_in_quote=False)
