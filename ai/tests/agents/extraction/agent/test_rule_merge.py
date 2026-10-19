"""모델 출력과 규칙 추출 결과 병합: (항목명, 값) 기준, 규칙이 모델 값을 덮지 않음 (#40, #90)."""

from app.agents.extraction import ExtractionAgent
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


def test_규칙_값이_다른_속성값의_부분문자열이어도_버려지지_않는다(stub_model, records):
    reply = ProductAttributes(attributes=[_attribute("모델번호", "AC-220V-A1")])

    result = _run(stub_model, reply, "정격전압 220V, 모델번호 AC-220V-A1")

    assert any(a.name == "모델번호" and a.value == "AC-220V-A1" for a in result.attributes)
    assert any(a.name == "정격전압" and a.value == "220V" for a in result.attributes)


def test_모델이_다른_항목에_같은_값을_담아도_규칙_결과가_사라지지_않는다(stub_model, records):
    result = _run(stub_model, ProductAttributes(attributes=[_attribute("모델명", "220V")]), "정격전압 220V")

    assert any(a.name == "모델명" and a.value == "220V" for a in result.attributes)
    assert any(a.name == "정격전압" and a.value == "220V" for a in result.attributes)


def test_모델이_이미_뽑은_값과_겹치는_규칙_결과는_중복으로_안_넣는다(stub_model, records):
    reply = ProductAttributes(attributes=[_attribute("인증정보", "CE-RoHS; CE-EMC(Electric)")])

    result = _run(stub_model, reply, "인증정보: CE-RoHS; CE-EMC(Electric)")

    assert len(result.attributes) == 1
