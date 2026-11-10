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


# #749 리뷰: 낱말을 건너뛸 때 숫자가 든 낱말·부정 표현을 넘으면 원문에 없는 값이 됨
@pytest.mark.parametrize("quote,value", [
    ("Input: 5V 1A, Output: 12V 2A", "5V 2A"),  # 원문에 없는 수치 조합
    ("정격 입력 5V 출력 12V", "입력 12V"),
    ("2.4GHz 출력 10mW, 5.8GHz 출력 25mW", "2.4GHz 25mW"),
    ("어린이용 아님, 성인용 탁상 선풍기", "어린이용 선풍기"),  # 부정을 건너뜀
    ("배터리 미포함, 어댑터 포함", "배터리 포함"),  # "포함"이 "미포함" 안에서 찾아지면 안 됨
    ("Wireless charging not supported", "wireless supported"),
    ("어린이용이 아니라 성인용 선풍기", "어린이용이 선풍기"),
    ("어댑터 없이 배터리로 작동", "어댑터 배터리로 작동"),
], ids=["수치_조합", "입력_출력_섞기", "주파수_출력_섞기", "부정_아님", "부정_미포함", "부정_not", "부정_아니라", "부정_없이"])
def test_숫자가_든_낱말이나_부정_표현을_건너뛴_값은_막는다(quote, value):
    assert not quote_matches(Fact(value, "q", quote), {"q": quote})


@pytest.mark.parametrize("quote,value", [
    ("EDC RFID 차단 초슬림 지갑 | 남녀공용 지퍼형 동전 주머니 | 다중 레이어 신용카드 홀더",
     "EDC RFID 차단 초슬림 지갑, 지퍼형 동전 주머니, 다중 레이어 신용카드 홀더"),  # 문장부호만 다름
    ("아기 수면등 무드등 선물용", "수면등, 무드등"),
    ("휴대용 무선 미니 선풍기", "휴대용 선풍기"),  # 수치·부정이 아닌 낱말은 여러 개 건너뛸 수 있음
    ("Input: 5V 1A, Output: 12V 2A", "12V 2A"),  # 이어서 있는 값은 그대로 통과
    ("2.4GHz 출력 10mW", "2.4GHz 10mW"),  # 수치 낱말 사이의 비수치 낱말은 건너뛸 수 있음
], ids=["쉼표_구분", "쉼표_두_낱말", "여러_낱말_생략", "이어진_수치", "수치_사이_낱말"])
def test_건너뛴_낱말이_수치나_부정이_아니면_받는다(quote, value):
    assert quote_matches(Fact(value, "q", quote), {"q": quote})


def test_판단_칸은_값을_보지_않고_인용만_본다():
    judged = Fact("예", "listing-2", "DC5V", field="battery_only")

    assert quote_matches(judged, SNIPPETS, value_in_quote=False)
    assert not quote_matches(Fact("예", "listing-2", "AC220V", field="battery_only"), SNIPPETS, value_in_quote=False)
