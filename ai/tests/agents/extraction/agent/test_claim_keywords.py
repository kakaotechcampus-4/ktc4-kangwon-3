"""판매자 글의 효능·미용 표방 문구를 코드 규칙으로 잡아 medical_claim·cosmetic_claim을 확정한다.

초안 50건 측정(2026-11-05)에서 모델은 제목의 '스트레스 완화', '가려움 완화', '관절을 안정화', '블랙헤드 제거',
'치아 미백 효과'를 표방으로 보지 않고 false로 뒀다(C1). 프롬프트는 이미 "상품 이름 안에 있어도 표방"이라고 하지만
gpt-4.1-mini가 따르지 않아, 표현이 분명한 문구만 규칙으로 확정한다. 부정("통증 없는 이어폰")과 촉감 설명("skin-friendly")은
표방이 아니라 잡지 않는다.
"""

import pytest

from app.agents.extraction import ExtractionAgent
from app.agents.extraction.guessed_flags import confirm_claims
from app.schemas.agent import ExtractionInput
from app.schemas.product import ProductAttributes


@pytest.mark.parametrize("text", [
    "비전동 플라스틱 반사요법 도구로 스트레스 완화",
    "건강한 모발 추출 및 가려움 완화를 위한 신성한 도구",
    "Feature 4: Headache Relif",
    "무릎 관절을 안정화시키는 일관된 압축을 제공하며",
    "슬리밍 지방 연소 뷰티 디바이스 체중 감소",
    "Cold Cooling Face Ice Massager for Morning Puffiness & Sunburn Relief",
    "굽은 등 교정기, 앉은 자세 교정 벨트",
    "여드름 치료 LED 마스크",
    "근육 이완 보드, 경락선 개통 마사지기",
    "혈액순환 개선에 도움",
])
def test_몸이_달라진다는_문구가_있으면_medical_claim을_true로_확정한다(text):
    attributes = {"medical_claim": False, "cosmetic_claim": None}

    assert "medical_claim" in confirm_claims(attributes, text)
    assert attributes["medical_claim"] is True


@pytest.mark.parametrize("text", [
    "[2pcs 치아 미백 칫솔] 치아 세정 및 미백 효과, 스테인 리무버 브러시",
    "USB 충전식 모공 클리너, 블랙헤드 제거 및 각질 마사저",
    "뷰티 디바이스 체중 감소 피부 탄력 강화",
    "얼굴 리프팅 및 탄력을 위한 미용 장치",
    "주름 개선 피부 재생, 피부톤 개선",
    "윤기 있고 촉촉한 머릿결을 만들어 줍니다",
    "Anion Hair Dryer for Smooth Hair Styling",
    "Cold Cooling Face Ice Massager for Morning Puffiness",
    "건강한 모발 추출 및 가려움 완화",
])
def test_겉모습이_달라진다는_문구가_있으면_cosmetic_claim을_true로_확정한다(text):
    attributes = {"medical_claim": None, "cosmetic_claim": False}

    assert "cosmetic_claim" in confirm_claims(attributes, text)
    assert attributes["cosmetic_claim"] is True


@pytest.mark.parametrize("text", [
    "ANKRIYUL 통증 없는 OWS 이어폰, 충전 케이스 포함",
    "본 제품은 의료 기기가 아닙니다",
    "skin-friendly silicone straws",
    "통기성 있고 안정적인 지지력 제공, 미끄럼방지 무릎 보호대",
    "커피나 모카 음료를 따뜻하게 유지해줘요",
    "소음 완화 설계, 사용성 개선",
    "피부에 직접 대지 마세요",
])
def test_부정·촉감·일반_문구는_표방으로_보지_않는다(text):
    attributes = {"medical_claim": False, "cosmetic_claim": False}

    assert confirm_claims(attributes, text) == []
    assert attributes == {"medical_claim": False, "cosmetic_claim": False}


def test_이미_true인_칸은_바꾼_목록에_넣지_않는다():
    attributes = {"medical_claim": True, "cosmetic_claim": True}

    assert confirm_claims(attributes, "통증 완화 미백 효과") == []


def test_추출_결과에_표방_확정이_적용된다(stub_model, records):
    reply = ProductAttributes(product_name="발 지압 매트", medical_claim=False)
    agent = ExtractionAgent(stub_model(reply))

    result = agent.run(ExtractionInput(product_id="p", text_blocks=["반사요법 도구로 스트레스 완화"]))

    assert result.medical_claim is True


# 초안 50건·기존 원문에 규칙을 오프라인으로 돌려 찾은 오탐·놓침 (2026-11-05)


@pytest.mark.parametrize("text", [
    "가벼운 무게감을 제공하여 장시간 스타일링 작업 시 팔의 피로를 줄여줍니다",
    "품목 유형\n교정기 및 지지대",
    "Raffles Quay, #14-06, Singapore (048580)",
    "uplifting music for shopping",
])
def test_인체공학_설명·카테고리_이름·영어_낱말_속_일치는_표방이_아니다(text):
    attributes = {"medical_claim": False, "cosmetic_claim": False}

    assert confirm_claims(attributes, text) == []


def test_판매자_전체_제목에만_있는_표방도_잡는다(stub_model, records, temu_page):
    # Temu는 잘린 제목 줄 뒤 구매 상자에 전체 제목이 있고, 판매자 구역 글에는 전체 제목이 빠질 수 있다.
    page = temu_page.replace("접이식 원목 의자 3단 높이 조절", "접이식 원목 의자 3단 높이 조절, 모공 클리너 블랙헤드 제거")
    agent = ExtractionAgent(stub_model(ProductAttributes(product_name="의자", cosmetic_claim=False)))

    result = agent.run(ExtractionInput(product_id="p", text_blocks=[page]))

    assert result.cosmetic_claim is True
