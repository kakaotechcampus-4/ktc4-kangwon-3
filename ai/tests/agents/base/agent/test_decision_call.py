"""BaseAgent 판단 호출: 판단 모델 준비, 판단 모델 이름·비용 기록, 실패 단계 (call·parsing).

판단 클라이언트는 실제 Jev 형식 클라이언트에 가짜 전송을 붙임. 실제 네트워크 요청은 보내지 않는다.
"""

import json

import httpx
import pytest

from app.agents.base import agent as agent_module
from app.clients.llm.decision import DecisionRequestError, DecisionResponseError, TypeSafeDecisionClient
from app.config import DECISION_PROFILES
from app.schemas.clients.decision_response import YesNoAnswer

JEV = "typesafe/jev-latest"
SUBJECT = {"product_name": "색연필 24색 세트"}
QUESTIONS = [{"type": "yes_no", "name": "kind_kids", "instructions": "어린이가 주로 쓰는 종류인가"}]


def _jev_reply(answers: dict) -> httpx.Response:
    return httpx.Response(200, json={
        "model": "typesafe/jev-1.14-20261014",
        "answers": answers,
        "usage": {"input_tokens": 1_000_000, "output_tokens": 0, "cached_prompt_tokens": 0, "cache_write_tokens": 0},
    })


def _decision_client(handler) -> TypeSafeDecisionClient:
    return TypeSafeDecisionClient("https://gateway.test/v1", "test-key", transport=httpx.MockTransport(handler))


def _agent(fakes, stub_model, handler):
    return fakes.Agent(
        stub_model(fakes.Answer(value="ok")), decision_client=_decision_client(handler), decision_model=JEV,
    )


def test_판단_답을_돌려주고_판단_모델_이름과_단가로_기록한다(fakes, stub_model, records):
    agent = _agent(fakes, stub_model, lambda request: _jev_reply({"kind_kids": {"type": "noul", "noul": 0.61}}))

    response, usage, started_at = agent._call_decision(SUBJECT, QUESTIONS, subject_id="p-1")
    meta = agent._finish_call(usage, "p-1", started_at, called_model=JEV)

    assert response.answers == {"kind_kids": YesNoAnswer(probability=0.61)}
    # 실제 버전은 사용량에, 기록·비용은 요청한 등록명으로
    assert usage.reported_model == "typesafe/jev-1.14-20261014"
    assert (meta.model, meta.reasoning_effort, meta.cost_krw, meta.failure_phase) == (JEV, None, 64.0, None)
    assert [(row["configured_model"], row["ok"]) for row in records] == [(JEV, True)]


def test_판단_호출_기록에는_채팅_프롬프트_지문을_남기지_않는다(fakes, stub_model, records):
    agent = _agent(fakes, stub_model, lambda request: _jev_reply({"kind_kids": {"type": "noul", "noul": 0.5}}))

    _, usage, started_at = agent._call_decision(SUBJECT, QUESTIONS, subject_id="p-1")
    decision_meta = agent._finish_call(usage, "p-1", started_at, called_model=JEV)
    chat_meta = agent.run_with_meta(fakes.question).meta

    # 판단 호출은 시스템 프롬프트를 안 씀. 같은 에이전트의 채팅 호출은 그대로 남김
    assert (decision_meta.prompt_name, decision_meta.prompt_sha256) == (None, None)
    assert (chat_meta.prompt_name, chat_meta.prompt_sha256) == (agent.prompt.name.value, agent.prompt.sha256)


def test_요청에_판단_모델_등록명을_넣는다(fakes, stub_model, records):
    sent = []

    def handler(request):
        sent.append(request)
        return _jev_reply({"kind_kids": {"type": "noul", "noul": 0.5}})

    _agent(fakes, stub_model, handler)._call_decision(SUBJECT, QUESTIONS, subject_id="p-1")

    assert json.loads(sent[0].content)["model"] == JEV


@pytest.mark.parametrize(("handler", "phase", "cause"), [
    (lambda request: httpx.Response(404, json={"error": {"code": "model_not_found"}}), "call", httpx.HTTPStatusError),
    (lambda request: _jev_reply({}), "parsing", DecisionResponseError),
], ids=["HTTP 오류", "답 누락"])
def test_판단_실패는_그_단계로_판단_모델_이름으로_기록하고_감싼다(fakes, stub_model, records, handler, phase, cause):
    agent = _agent(fakes, stub_model, handler)

    with pytest.raises(fakes.Error) as caught:
        agent._call_decision(SUBJECT, QUESTIONS, subject_id="p-1", partial_result="부분")

    assert isinstance(caught.value.__cause__, cause)
    assert (caught.value.meta.model, caught.value.meta.failure_phase) == (JEV, phase)
    assert caught.value.partial_result == "부분"
    assert [(row["configured_model"], row["ok"], row["failure_phase"]) for row in records] == [(JEV, False, phase)]


@pytest.mark.parametrize(("handler", "message"), [
    (lambda request: httpx.Response(500, text="server error"), "가짜 작업 판단 모델 호출에 실패했습니다"),
    (lambda request: _jev_reply({}), "가짜 작업 판단 모델 응답을 해석하지 못했습니다"),
], ids=["호출 실패", "응답 해석 실패"])
def test_판단_실패_문구는_채팅_출력_스키마가_아니라_판단_모델로_쓴다(fakes, stub_model, records, handler, message):
    agent = _agent(fakes, stub_model, handler)

    with pytest.raises(fakes.Error, match=message) as caught:
        agent._call_decision(SUBJECT, QUESTIONS, subject_id="p-1")
    assert "Answer 스키마" not in str(caught.value)


def test_답을_못_쓴_판단_응답도_쓴_토큰과_비용을_기록한다(fakes, stub_model, records):
    agent = _agent(fakes, stub_model, lambda request: _jev_reply({}))

    with pytest.raises(fakes.Error) as caught:
        agent._call_decision(SUBJECT, QUESTIONS, subject_id="p-1")

    assert caught.value.meta.failure_phase == "parsing"
    assert (caught.value.meta.usage.input_tokens, caught.value.meta.cost_krw) == (1_000_000, 64.0)
    assert records[0]["usage"].reported_model == "typesafe/jev-1.14-20261014"


def test_HTTP_오류는_응답이_없어_사용량_없이_기록한다(fakes, stub_model, records):
    agent = _agent(fakes, stub_model, lambda request: httpx.Response(500, text="server error"))

    with pytest.raises(fakes.Error) as caught:
        agent._call_decision(SUBJECT, QUESTIONS, subject_id="p-1")

    assert (caught.value.meta.failure_phase, caught.value.meta.usage, records[0]["usage"]) == ("call", None, None)


def test_판단_프로필이_없는_에이전트는_판단_호출을_막는다(fakes, stub_model, records):
    agent = fakes.Agent(stub_model(fakes.Answer(value="ok")))

    with pytest.raises(RuntimeError, match="판단 모델 없이"):
        agent._call_decision(SUBJECT, QUESTIONS, subject_id="p-1")
    assert records == []


def test_판단_프로필이_있으면_첫_판단_호출_때_공유_클라이언트를_가져온다(fakes, stub_model, records, monkeypatch):
    fetched = []
    shared = _decision_client(lambda request: _jev_reply({"kind_kids": {"type": "noul", "noul": 0.5}}))
    monkeypatch.setattr(agent_module, "agent_decision_profile", lambda name: DECISION_PROFILES["jev"])
    monkeypatch.setattr(agent_module, "get_decision_client", lambda profile: fetched.append(profile) or shared)

    agent = fakes.Agent(stub_model(fakes.Answer(value="ok")))
    # 만들 때는 설정을 읽지 않음 (모델을 주입한 테스트가 .env 없이도 돌게)
    assert (fetched, agent._decision_model) == ([], JEV)

    agent._call_decision(SUBJECT, QUESTIONS, subject_id="p-1")
    agent._call_decision(SUBJECT, QUESTIONS, subject_id="p-1")

    assert fetched == [DECISION_PROFILES["jev"]]


def test_판단_클라이언트만_주고_등록명을_안_주면_만들_때_실패한다(fakes, stub_model):
    with pytest.raises(ValueError, match="decision_model"):
        fakes.Agent(stub_model(fakes.Answer(value="ok")), decision_client=_decision_client(lambda request: None))


def test_이름이_겹치는_질문은_보내지도_기록하지도_않는다(fakes, stub_model, records):
    sent = []
    agent = _agent(fakes, stub_model, lambda request: sent.append(request))

    # 코드 오류라 모델 실패로 감싸지 않고 그대로 올림
    with pytest.raises(DecisionRequestError):
        agent._call_decision(SUBJECT, QUESTIONS * 2, subject_id="p-1")
    assert (sent, records) == ([], [])
