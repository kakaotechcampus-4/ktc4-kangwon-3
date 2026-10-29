"""판단 클라이언트 공통 베이스가 경로·인증으로 보내고, 잘못된 응답을 DecisionResponseError로 바꾸는지 확인한다.

제공사 형식과 무관한 동작이라 가짜 하위 클라이언트로 확인. 실제 네트워크 요청은 보내지 않는다.
"""

import httpx
import pytest

from app.clients.llm.decision import DecisionClient, DecisionRequestError, DecisionResponseError
from app.schemas.clients.decision_request import DecisionRequest
from app.schemas.clients.decision_response import DecisionUsage

from .conftest import API_KEY, BASE_URL


class _EchoDecisionClient(DecisionClient):
    """요청 모델만 보내고, 응답 본문을 공통 답 모양 그대로 읽는 가짜 하위 클라이언트."""

    def _to_payload(self, request: DecisionRequest) -> dict:
        return {"model": request.model}

    def _usage_from_payload(self, body: dict) -> DecisionUsage:
        return DecisionUsage(model=body["model"], input_tokens=body["input_tokens"])

    def _answers_from_payload(self, body: dict) -> dict:
        return body["answers"]


def _answers(*names: str) -> dict:
    return {name: {"type": "refused"} for name in names}


def _ok(*names: str) -> httpx.Response:
    return httpx.Response(200, json={"model": "m", "answers": _answers(*names), "input_tokens": 10})


ALL_NAMES = ("kind_kids", "category", "kid_use")


def test_게이트웨이_decisions_경로로_인증_헤더와_함께_보낸다(wire, decision_request):
    client = _EchoDecisionClient(BASE_URL + "/", API_KEY)
    sent = wire(client, lambda request: _ok(*ALL_NAMES))

    client.decide(decision_request)

    [request] = sent
    assert (request.method, str(request.url)) == ("POST", "https://gateway.test/v1/decisions")
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"


def test_답이_빠진_질문이_있으면_이름을_담아_실패한다(wire, decision_request):
    client = _EchoDecisionClient(BASE_URL, API_KEY)
    wire(client, lambda request: _ok("kind_kids"))

    with pytest.raises(DecisionResponseError, match="category"):
        client.decide(decision_request)


@pytest.mark.parametrize("response", [
    httpx.Response(200, text="Not Found"),
    httpx.Response(200, json=["목록"]),
    httpx.Response(200, json={"answers": {}}),
    httpx.Response(200, json={"model": "m", "answers": {"kind_kids": {"type": "box"}}, "input_tokens": 1}),
], ids=["JSON 아님", "객체 아님", "필드 누락", "모르는 답 종류"])
def test_변환할_수_없는_응답은_DecisionResponseError(wire, decision_request, response):
    client = _EchoDecisionClient(BASE_URL, API_KEY)
    wire(client, lambda request: response)

    with pytest.raises(DecisionResponseError):
        client.decide(decision_request)


def test_HTTP_오류는_HTTPStatusError_그대로(wire, decision_request):
    client = _EchoDecisionClient(BASE_URL, API_KEY)
    wire(client, lambda request: httpx.Response(404, json={"error": {"code": "model_not_found"}}))

    with pytest.raises(httpx.HTTPStatusError):
        client.decide(decision_request)


@pytest.mark.parametrize(("questions", "message"), [
    ([
        {"type": "yes_no", "name": "q", "instructions": "A인가"},
        {"type": "yes_no", "name": "q", "instructions": "B인가"},
    ], "질문 이름 중복"),
    ([
        {"type": "choice", "name": "c", "instructions": "종류",
         "options": [{"value": "a", "description": "1"}, {"value": "a", "description": "2"}]},
    ], "c의 후보·단계 값 중복"),
    ([
        {"type": "score", "name": "s", "instructions": "정도", "levels": [{"value": "low"}, {"value": "low"}]},
    ], "s의 후보·단계 값 중복"),
], ids=["질문 이름", "고르기 후보", "점수 단계"])
def test_이름이나_값이_겹치는_요청은_보내지_않고_실패한다(wire, questions, message):
    # Jev는 이름 키 맵으로 보내 겹치면 앞 질문·후보가 덮이고, 답도 이름으로 찾아 섞임
    client = _EchoDecisionClient(BASE_URL, API_KEY)
    sent = wire(client, lambda request: _ok("q"))
    request = DecisionRequest(model="m", subject={}, questions=questions)

    with pytest.raises(DecisionRequestError, match=message):
        client.decide(request)
    assert sent == []


@pytest.mark.parametrize(("body", "message"), [
    ({"model": "m", "answers": {"kind_kids": {"type": "box"}}, "input_tokens": 10}, "답 변환 실패"),
    ({"model": "m", "answers": _answers("kind_kids"), "input_tokens": 10}, "답이 없는 질문"),
], ids=["답 변환 실패", "답 누락"])
def test_답을_못_쓰는_응답도_읽은_사용량을_예외에_담는다(wire, decision_request, body, message):
    client = _EchoDecisionClient(BASE_URL, API_KEY)
    wire(client, lambda request: httpx.Response(200, json=body))

    with pytest.raises(DecisionResponseError, match=message) as caught:
        client.decide(decision_request)
    assert caught.value.usage == DecisionUsage(model="m", input_tokens=10)


def test_사용량을_못_읽으면_예외의_사용량은_None(wire, decision_request):
    client = _EchoDecisionClient(BASE_URL, API_KEY)
    wire(client, lambda request: httpx.Response(200, json={"model": "m", "answers": {}}))

    with pytest.raises(DecisionResponseError, match="사용량 변환 실패") as caught:
        client.decide(decision_request)
    assert caught.value.usage is None
