"""SelectionAgent 입출력: 6개 Tool 판단 반환, 상품 JSON 메시지, 사용량 기록 이름."""

import contextlib
import json

import pytest

from app.agents.selection import SelectionAgent, SelectionFailedError
from app.schemas.agent import ToolSelectionItem, ToolSelectionResponse
from app.schemas.product import Product
from app.schemas.schemas import ToolName

_PRODUCT = Product(product_id="test-001", source_url=None)


def _response(*selected: ToolName) -> ToolSelectionResponse:
    return ToolSelectionResponse(decisions=[
        ToolSelectionItem(tool_name=name, selected=name in selected, reason=f"{name} 판단") for name in ToolName
    ])


def test_모델이_낸_6개_Tool_판단을_그대로_돌려준다(stub_model, records):
    result = SelectionAgent(stub_model(_response(ToolName.CUSTOMS, ToolName.ELECTRICAL))).run(_PRODUCT)

    assert [d.tool_name for d in result.decisions] == list(ToolName)
    assert {d.tool_name for d in result.decisions if d.selected} == {ToolName.CUSTOMS, ToolName.ELECTRICAL}


def test_상품_정보를_JSON으로_사용자_메시지에_담는다(stub_model, records):
    model = stub_model(_response())
    product = Product(product_id="test-001", source_url=None, product_name="테스트 상품", electrical_powered=True)

    SelectionAgent(model).run(product)

    payload = json.loads(model.received[0][-1].content)
    assert (payload["product_id"], payload["product_name"], payload["electrical_powered"]) == ("test-001", "테스트 상품", True)


def test_모르는_값은_빠뜨리지_않고_null로_보내_false와_구분한다(stub_model, records):
    # 프롬프트 규칙: None은 "없다"가 아니라 정보 부족 → 키가 빠지면 모델이 구분 못 함
    model = stub_model(_response())

    SelectionAgent(model).run(Product(product_id="test-001", source_url=None, wireless_comm=False))

    payload = json.loads(model.received[0][-1].content)
    assert (payload["wireless_comm"], payload["for_children"]) == (False, None)
    assert "for_children" in payload


def test_시스템_프롬프트는_선택_프롬프트를_쓴다(stub_model, records):
    model = stub_model(_response())

    SelectionAgent(model).run(_PRODUCT)

    assert "6개 심사 도메인" in model.received[0][0].content


def test_6개가_아닌_응답은_SelectionFailedError로_감싼다(stub_model, records):
    # Tool 실행기가 6개 판단을 전제로 함. 빠진 Tool은 KeyError 대신 선택 실패로
    reply = {"decisions": [{"tool_name": "customs_requirements", "selected": True, "reason": "통관"}]}

    with pytest.raises(SelectionFailedError):
        SelectionAgent(stub_model(reply)).run(_PRODUCT)


def test_사용량은_상품_ID로_선택_이름에_기록한다(stub_model, records):
    SelectionAgent(stub_model(_response())).run(Product(product_id="prod-usage-1", source_url=None))

    assert (records[0]["agent"], records[0]["subject_id"]) == ("selection", "prod-usage-1")


def test_평가_실행은_운영과_다른_이름으로_집계된다(stub_model, records):
    SelectionAgent(stub_model(_response()), usage_agent="selection-eval").run(_PRODUCT)

    assert records[0]["agent"] == "selection-eval"


def test_요청_본문은_선택_스키마_클래스를_넘길_때와_같다(fake_gateway, records):
    product = Product(product_id="test-001", source_url=None, product_name="USB 선풍기", electrical_powered=True)
    actual: list[dict] = []
    agent = SelectionAgent(fake_gateway("{}", "stop", actual))
    expected: list[dict] = []
    reference = fake_gateway("{}", "stop", expected).with_structured_output(ToolSelectionResponse, include_raw=True)

    # 응답 "{}"는 스키마와 맞지 않아 양쪽 모두 실패하지만 요청 본문은 이미 기록됨
    with contextlib.suppress(Exception):
        reference.invoke(agent._build_messages(product))
    with pytest.raises(SelectionFailedError):
        agent.run(product)

    assert actual == expected
