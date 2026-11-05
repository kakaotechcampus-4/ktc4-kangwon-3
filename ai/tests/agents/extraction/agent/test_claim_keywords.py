"""판매자 글의 효능·미용 표방 문구와 어긋나는 medical_claim·cosmetic_claim false를 '애매함'(None)으로 되돌린다.

초안 50건 측정(2026-11-05)에서 모델은 제목의 '스트레스 완화', '가려움 완화', '관절을 안정화', '블랙헤드 제거',
'치아 미백 효과'를 표방으로 보지 않고 false로 뒀다(C1). 코드는 표방 여부를 대신 정하지 않는다(true로 확정하지 않음).
페이지 문구와 모델의 false가 어긋나는 명확한 경우만 None으로 돌리고, 근거 문구를 conflicts에 남겨 판단 단계로 넘긴다.
부정("통증 없는 이어폰")과 촉감 설명("skin-friendly")은 표방이 아니라 잡지 않는다.
"""

import pytest

from app.agents.extraction import ExtractionAgent
from app.agents.extraction.guessed_flags import drop_contradicted_claim_false
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
def test_몸이_달라진다는_문구와_어긋나는_medical_claim_false는_모름으로_되돌린다(text):
    attributes = {"medical_claim": False, "cosmetic_claim": None}

    dropped, conflicts = drop_contradicted_claim_false(attributes, text)

    assert dropped == ["medical_claim"]
    assert attributes["medical_claim"] is None
    assert len(conflicts) == 1


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
def test_겉모습이_달라진다는_문구와_어긋나는_cosmetic_claim_false는_모름으로_되돌린다(text):
    attributes = {"medical_claim": None, "cosmetic_claim": False}

    dropped, _ = drop_contradicted_claim_false(attributes, text)

    assert "cosmetic_claim" in dropped
    assert attributes["cosmetic_claim"] is None


def test_모순_문장에는_근거가_된_판매자_문구를_그대로_담는다():
    attributes = {"medical_claim": False, "cosmetic_claim": False}

    _, conflicts = drop_contradicted_claim_false(attributes, "발 지압 매트, 반사요법 도구로 스트레스 완화")

    assert conflicts == ['판매자 문구 "스트레스 완화"가 효능 표방일 수 있어 확인이 필요합니다.']


@pytest.mark.parametrize("value", [None, True])
def test_코드는_표방을_true로_확정하지_않고_모름이나_true는_그대로_둔다(value):
    # 코드는 명확한 오류(근거와 어긋나는 false)를 애매함으로 돌리는 안전장치까지만 한다.
    attributes = {"medical_claim": value, "cosmetic_claim": value}

    assert drop_contradicted_claim_false(attributes, "통증 완화 미백 효과") == ([], [])
    assert attributes == {"medical_claim": value, "cosmetic_claim": value}


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

    assert drop_contradicted_claim_false(attributes, text) == ([], [])
    assert attributes == {"medical_claim": False, "cosmetic_claim": False}


def test_추출_결과에_표방_false_되돌리기가_적용되고_모순으로_남는다(stub_model, records):
    reply = ProductAttributes(product_name="발 지압 매트", medical_claim=False)
    agent = ExtractionAgent(stub_model(reply))

    result = agent.run(ExtractionInput(product_id="p", text_blocks=["반사요법 도구로 스트레스 완화"]))

    assert result.medical_claim is None
    assert any("스트레스 완화" in c for c in result.conflicts)


# 초안 50건·기존 원문에 규칙을 오프라인으로 돌려 찾은 오탐·놓침 (2026-11-05)


@pytest.mark.parametrize("text", [
    "가벼운 무게감을 제공하여 장시간 스타일링 작업 시 팔의 피로를 줄여줍니다",
    "품목 유형\n교정기 및 지지대",
    "Raffles Quay, #14-06, Singapore (048580)",
    "uplifting music for shopping",
])
def test_인체공학_설명·카테고리_이름·영어_낱말_속_일치는_표방이_아니다(text):
    attributes = {"medical_claim": False, "cosmetic_claim": False}

    assert drop_contradicted_claim_false(attributes, text) == ([], [])


def test_판매자_전체_제목에만_있는_표방도_잡는다(stub_model, records, temu_page):
    # Temu는 잘린 제목 줄 뒤 구매 상자에 전체 제목이 있고, 판매자 구역 글에는 전체 제목이 빠질 수 있다.
    page = temu_page.replace("접이식 원목 의자 3단 높이 조절", "접이식 원목 의자 3단 높이 조절, 모공 클리너 블랙헤드 제거")
    agent = ExtractionAgent(stub_model(ProductAttributes(product_name="의자", cosmetic_claim=False)))

    result = agent.run(ExtractionInput(product_id="p", text_blocks=[page]))

    assert result.cosmetic_claim is None
