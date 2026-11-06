"""모델 출력과 규칙 추출 결과 병합: (항목명, 값) 기준, 규칙이 모델 값을 덮지 않음 (#40, #90)."""

from app.agents.extraction import ExtractionAgent
from app.agents.extraction.rules import detect_battery_capacity_conflict
from app.schemas.agent import ExtractionInput
from app.schemas.product import ProductAttributes


def _attribute(name: str, value: str) -> dict:
    return {"name": name, "value": value, "source_text": None, "source_url": None}


def _run(stub_model, reply: ProductAttributes, *text_blocks: str):
    return ExtractionAgent(stub_model(reply)).run(ExtractionInput(product_id="prod-merge", text_blocks=list(text_blocks)))


def test_모델이_놓친_배터리_모순도_규칙이_잡아_conflicts에_담긴다(stub_model, records):
    # 파워뱅크 케이스 패턴: 용량 표기 + 배터리 미포함
    result = _run(stub_model, ProductAttributes(product_name="MagSafe 케이스"), "MagSafe 1460mAh 케이스", "배터리 속성 배터리 미포함")

    assert len(result.conflicts) == 1
    assert "1460mAh" in result.conflicts[0]
    assert any(a.name == "배터리 용량" and a.value == "1460mAh" for a in result.attributes)


def test_모델과_규칙이_같은_모순을_내면_한_번만_남긴다(stub_model, records):
    text_blocks = ["MagSafe 1460mAh 케이스", "배터리 속성 배터리 미포함"]
    [rule_conflict] = detect_battery_capacity_conflict(text_blocks)
    reply = ProductAttributes(conflicts=["모델이 먼저 찾은 모순", rule_conflict])

    result = _run(stub_model, reply, *text_blocks)

    # 모델 것이 먼저, 같은 문장은 중복 없이
    assert result.conflicts == ["모델이 먼저 찾은 모순", rule_conflict]


def test_규칙_값이_다른_속성값의_부분문자열이어도_버려지지_않는다(stub_model, records):
    reply = ProductAttributes(attributes=[_attribute("모델번호", "AC-220V-A1")])

    result = _run(stub_model, reply, "정격전압 220V, 모델번호 AC-220V-A1")

    assert any(a.name == "모델번호" and a.value == "AC-220V-A1" for a in result.attributes)
    assert any(a.name == "전압 표기" and a.value == "220V" for a in result.attributes)


def test_모델이_다른_항목에_같은_값을_담아도_규칙_결과가_사라지지_않는다(stub_model, records):
    result = _run(stub_model, ProductAttributes(attributes=[_attribute("모델명", "220V")]), "정격전압 220V")

    assert any(a.name == "모델명" and a.value == "220V" for a in result.attributes)
    assert any(a.name == "전압 표기" and a.value == "220V" for a in result.attributes)


def test_모델이_이미_뽑은_값과_겹치는_규칙_결과는_중복으로_안_넣는다(stub_model, records):
    reply = ProductAttributes(attributes=[_attribute("인증정보", "CE-RoHS; CE-EMC(Electric)")])

    result = _run(stub_model, reply, "인증정보: CE-RoHS; CE-EMC(Electric)")

    assert len(result.attributes) == 1


def test_모델이_놓친_스펙표_전원_모순도_규칙이_잡아_conflicts에_담긴다(stub_model, records):
    # 초안 50건 측정(2026-11-05)에서 모델은 제목↔스펙표 모순을 보고하지 않았다. 규칙이 대신 잡는다.
    result = _run(stub_model, ProductAttributes(product_name="바디 마사지기"), "전자식\n아니요\n전원 공급\n교류")

    assert len(result.conflicts) == 1
    assert "전자식" in result.conflicts[0] and "교류" in result.conflicts[0]


def test_판매자_제목과_스펙표_재질이_다르면_규칙이_모순으로_담는다(stub_model, records, temu_page):
    page = temu_page.replace("재료: 원목", "재료: 플라스틱")

    result = _run(stub_model, ProductAttributes(product_name="접이식 의자"), page)

    assert any("원목" in c and "플라스틱" in c for c in result.conflicts)
