"""SelectionAgent 동작 검증. 실제 OpenAI 호출 없이 모델을 스텁으로 대체한다."""

import json
import logging
from types import SimpleNamespace

import pytest

from app.schemas.agent import ToolSelectionItem, ToolSelectionResponse
from app.schemas.product import Product
from app.schemas.schemas import ToolName
from app.agents.selection import SelectionAgent, SelectionFailedError


def _make_product(**overrides) -> Product:
    """테스트용 Product를 최소 필드로 만든다."""
    defaults = dict(product_id="test-001", source_url=None)
    defaults.update(overrides)
    return Product(**defaults)


def _make_all_selected_response() -> ToolSelectionResponse:
    """6개 도메인 전부 selected=True인 응답."""
    return ToolSelectionResponse(
        decisions=[
            ToolSelectionItem(tool_name=name, selected=True, reason=f"{name} 검토 필요")
            for name in ToolName
        ]
    )


def _make_mixed_response() -> ToolSelectionResponse:
    """통관·전기만 선택, 나머지 미선택."""
    decisions = []
    for name in ToolName:
        selected = name in (ToolName.CUSTOMS, ToolName.ELECTRICAL)
        decisions.append(
            ToolSelectionItem(
                tool_name=name,
                selected=selected,
                reason=f"{name} {'검토 필요' if selected else '해당 없음'}",
            )
        )
    return ToolSelectionResponse(decisions=decisions)


_FAKE_USAGE = {
    "input_tokens": 3000,
    "output_tokens": 400,
    "total_tokens": 3400,
    "input_token_details": {"cache_read": 1800},
}


class _StubChatModel:
    """with_structured_output(..., include_raw=True).invoke(...) 인터페이스만 흉내 낸 스텁."""

    def __init__(
        self,
        result: ToolSelectionResponse | None,
        parsing_error: Exception | None = None,
    ) -> None:
        self._result = result
        self._parsing_error = parsing_error
        self.received_messages: list | None = None

    def with_structured_output(self, schema: type, include_raw: bool = False) -> "_StubChatModel":
        assert schema is ToolSelectionResponse
        assert include_raw is True
        return self

    def invoke(self, messages: list) -> dict:
        self.received_messages = messages
        return {
            "raw": SimpleNamespace(usage_metadata=_FAKE_USAGE, response_metadata={}),
            "parsed": self._result,
            "parsing_error": self._parsing_error,
        }


class _RaisingChatModel:
    """모델 호출 실패(레이트리밋·인증 오류 등)를 흉내 낸다."""

    def with_structured_output(self, schema: type, include_raw: bool = False) -> "_RaisingChatModel":
        return self

    def invoke(self, messages: list) -> dict:
        raise RuntimeError("rate limit exceeded")


def test_6개_도메인_전부_선택한_응답이_그대로_반환된다():
    response = _make_all_selected_response()
    agent = SelectionAgent(model=_StubChatModel(response))

    result = agent.select(_make_product())

    assert isinstance(result, ToolSelectionResponse)
    assert len(result.decisions) == 6
    assert all(d.selected for d in result.decisions)


def test_선택과_미선택이_섞인_응답도_정상_반환된다():
    response = _make_mixed_response()
    agent = SelectionAgent(model=_StubChatModel(response))

    result = agent.select(_make_product())

    selected_names = {d.tool_name for d in result.decisions if d.selected}
    assert selected_names == {ToolName.CUSTOMS, ToolName.ELECTRICAL}


def test_Product가_JSON으로_직렬화되어_HumanMessage에_전달된다():
    stub_model = _StubChatModel(_make_all_selected_response())
    agent = SelectionAgent(model=stub_model)
    product = _make_product(product_name="테스트 상품", electrical_powered=True)

    agent.select(product)

    assert stub_model.received_messages is not None
    human_message = stub_model.received_messages[-1]
    payload = json.loads(human_message.content)
    assert payload["product_id"] == "test-001"
    assert payload["product_name"] == "테스트 상품"
    assert payload["electrical_powered"] is True


def test_시스템_프롬프트가_selection_md에서_로드된다():
    stub_model = _StubChatModel(_make_all_selected_response())
    agent = SelectionAgent(model=stub_model)

    agent.select(_make_product())

    system_message = stub_model.received_messages[0]
    assert "선택 에이전트" in system_message.content
    assert "6개 심사 도메인" in system_message.content


def test_모델_호출이_실패하면_SelectionFailedError로_감싸진다():
    agent = SelectionAgent(model=_RaisingChatModel())

    with pytest.raises(SelectionFailedError) as exc_info:
        agent.select(_make_product())

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "rate limit exceeded" in str(exc_info.value.__cause__)


def test_모델_응답이_스키마와_안_맞으면_SelectionFailedError를_낸다():
    stub_model = _StubChatModel(result=None, parsing_error=ValueError("field required"))
    agent = SelectionAgent(model=stub_model)

    with pytest.raises(SelectionFailedError) as exc_info:
        agent.select(_make_product())

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_토큰_사용량과_캐시_적용량이_로그에_남는다(caplog):
    agent = SelectionAgent(model=_StubChatModel(_make_all_selected_response()))

    with caplog.at_level(logging.INFO, logger="app.agents.selection"):
        agent.select(_make_product())

    assert "input=3000" in caplog.text
    assert "cache_read=1800" in caplog.text
    assert "output=400" in caplog.text


def test_모델을_주입하지_않으면_공통_설정의_build_chat_model을_쓴다(monkeypatch):
    calls: list = []

    class _FakeModel:
        def with_structured_output(self, schema: type, include_raw: bool = False):
            calls.append((schema, include_raw))
            return self

    monkeypatch.setattr("app.agents.selection.build_chat_model", lambda: _FakeModel())

    SelectionAgent()

    assert calls == [(ToolSelectionResponse, True)]


def test_ToolSelectionResponse는_6개_미만이면_거부한다():
    with pytest.raises(ValueError, match="6개 심사 툴"):
        ToolSelectionResponse(
            decisions=[
                ToolSelectionItem(tool_name=ToolName.CUSTOMS, selected=True, reason="통관"),
            ]
        )


def test_ToolSelectionResponse는_중복_도메인을_거부한다():
    with pytest.raises(ValueError, match="6개 심사 툴"):
        ToolSelectionResponse(
            decisions=[
                ToolSelectionItem(tool_name=ToolName.CUSTOMS, selected=True, reason="통관"),
                ToolSelectionItem(tool_name=ToolName.CUSTOMS, selected=True, reason="통관 중복"),
                ToolSelectionItem(tool_name=ToolName.RADIO, selected=False, reason="전파 아님"),
                ToolSelectionItem(tool_name=ToolName.FOOD_DRUG, selected=False, reason="식약 아님"),
                ToolSelectionItem(tool_name=ToolName.ELECTRICAL, selected=True, reason="전기"),
                ToolSelectionItem(tool_name=ToolName.CHILDREN, selected=False, reason="어린이 아님"),
            ]
        )
