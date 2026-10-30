"""DecisionSelectionAgent: 판단 모델 한 번으로 6개 Tool 선택, 보내는 정보, 기록, 실패, 설정 검사.

판단 클라이언트는 실제 Jev 형식 클라이언트에 가짜 전송을 붙임. 실제 네트워크 요청은 보내지 않는다.
"""

import json

import httpx
import pytest

from app.agents.decision_selection import QUESTIONS, DecisionSelectionAgent
from app.clients.llm.decision import TypeSafeDecisionClient, questions_fingerprint
from app.config import ConfigError
from app.schemas.product import Product
from app.schemas.schemas import ToolName

JEV = "typesafe/jev-latest"
_PRODUCT = Product(product_id="p-1", source_url="https://shop.test/1", product_name="색연필 24색 세트",
                   wireless_comm=False, wireless_charging=False, wireless_shield=False)


def _jev_reply(**probabilities) -> httpx.Response:
    answers = {question.name: {"type": "noul", "noul": probabilities.get(question.name, 0.05)} for question in QUESTIONS}
    return httpx.Response(200, json={
        "model": "typesafe/jev-1.14-20261014",
        "answers": answers,
        "usage": {"input_tokens": 1000, "output_tokens": 0},
    })


def _agent(handler) -> DecisionSelectionAgent:
    client = TypeSafeDecisionClient("https://gateway.test/v1", "test-key", transport=httpx.MockTransport(handler))
    return DecisionSelectionAgent(decision_client=client, decision_model=JEV)


def test_판단_답으로_6개_Tool_선택을_돌려주고_한_번_기록한다(records):
    result = _agent(lambda request: _jev_reply(children_kind=0.82)).run_with_meta(_PRODUCT)

    picked = {item.tool_name for item in result.result.decisions if item.selected}
    assert picked == {ToolName.CUSTOMS, ToolName.CHILDREN}
    assert (result.meta.model, result.meta.prompt_sha256) == (JEV, questions_fingerprint(list(QUESTIONS)))
    assert [(row["agent"], row["ok"]) for row in records] == [("decision_selection", True)]


def test_식별_필드는_빼고_전체_질문을_한_요청으로_보낸다(records):
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return _jev_reply()

    _agent(handler).run(_PRODUCT)

    assert len(sent) == 1
    assert sent[0]["state"]["product_name"] == "색연필 24색 세트"
    assert not {"product_id", "source_url"} & set(sent[0]["state"])
    assert list(sent[0]["questions"]) == [question.name for question in QUESTIONS]


@pytest.mark.parametrize(("reply", "phase"), [
    (httpx.Response(500, text="server error"), "call"),
    (httpx.Response(200, json={"model": "typesafe/jev-1.14-20261014", "answers": {},
                               "usage": {"input_tokens": 1000, "output_tokens": 0}}), "parsing"),
])
def test_판단_호출이_실패하면_실패로_기록하고_전부_선택한다(records, reply, phase):
    result = _agent(lambda request: reply).run_with_meta(_PRODUCT)

    assert all(item.selected for item in result.result.decisions)
    reasons = {item.tool_name: item.reason for item in result.result.decisions}
    assert reasons[ToolName.CUSTOMS] == "규칙: 해외 직구 상품은 수입 통관 대상"
    assert reasons[ToolName.CHILDREN] == "규칙 해당 없음. 판단 모델 호출 실패로 정보 부족, 선택"
    assert result.meta.failure_phase == phase
    assert [(row["ok"], row["failure_phase"]) for row in records] == [(False, phase)]


def test_조립이_실패하면_실패로_기록하고_예외를_그대로_던진다(records, monkeypatch):
    monkeypatch.setattr("app.agents.decision_selection.agent.assemble", _raise_value_error)

    with pytest.raises(ValueError, match="조립 실패"):
        _agent(lambda request: _jev_reply()).run(_PRODUCT)

    assert [(row["ok"], row["failure_phase"]) for row in records] == [(False, "finalize")]


def _raise_value_error(*args):
    raise ValueError("조립 실패")


def test_사용량_기록_이름을_바꿀_수_있다(records):
    client = TypeSafeDecisionClient("https://gateway.test/v1", "test-key",
                                    transport=httpx.MockTransport(lambda request: _jev_reply()))

    DecisionSelectionAgent(usage_agent="decision-selection-eval", decision_client=client, decision_model=JEV).run(
        _PRODUCT)

    assert [row["agent"] for row in records] == ["decision-selection-eval"]


def test_기본_판단_모델은_프로필로_고른다():
    assert DecisionSelectionAgent()._decision_model == JEV


def test_판단_프로필이_없으면_만들_때_막는다(monkeypatch):
    monkeypatch.setattr("app.config.chat.AGENT_DECISION_PROFILES", {})

    with pytest.raises(ConfigError, match="판단 모델 프로필이 정해지지 않았습니다"):
        DecisionSelectionAgent()


def test_문턱값이_없는_판단_모델이면_만들_때_막는다():
    client = TypeSafeDecisionClient("https://gateway.test/v1", "test-key")

    with pytest.raises(ConfigError, match="문턱값이 정해지지 않은 판단 모델입니다"):
        DecisionSelectionAgent(decision_client=client, decision_model="unknown/model")
