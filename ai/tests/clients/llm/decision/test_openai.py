"""Luna(OpenAI) 판단 클라이언트가 공통 요청을 OpenAI 본문으로, OpenAI 응답을 공통 응답으로 바꾸는지 확인한다.

응답 본문은 2026-10-29 실제 Luna 응답 모양. 실제 네트워크 요청은 보내지 않는다.
"""

import json

import httpx
import pytest

from app.clients.llm.decision import DecisionResponseError
from app.clients.llm.decision.openai import OpenAIDecisionClient
from app.schemas.clients.decision_response import ChoiceAnswer, RefusedAnswer, ScoreAnswer, YesNoAnswer

from .conftest import API_KEY, BASE_URL

LUNA_BODY = {
    "model": "gpt-6-luna",
    "answers": [
        {"type": "predicate", "name": "kind_kids", "probability": 0.94},
        {
            "type": "choice", "name": "category", "choice": "stationery",
            "probabilities": [{"value": "stationery", "probability": 1.0}, {"value": "other", "probability": 0.0}],
            "confidence": 1.0,
        },
        {
            "type": "score", "name": "kid_use", "score": 0.86,
            "probabilities": [
                {"value": 2, "label": "high", "probability": 0.2},
                {"value": 0, "label": "low", "probability": 0.34},
                {"value": 1, "label": "mid", "probability": 0.46},
            ],
            "confidence": 0.19,
        },
    ],
    "usage": {
        "input_tokens": 419, "input_tokens_details": {"cached_tokens": 100, "cache_write_tokens": 20},
        "output_tokens": 0, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 419,
    },
}


@pytest.fixture
def client() -> OpenAIDecisionClient:
    return OpenAIDecisionClient(BASE_URL, API_KEY)


def test_판단_대상은_input_json_파트로_질문은_배열로_보낸다(wire, client, decision_request):
    sent = wire(client, lambda request: httpx.Response(200, json=LUNA_BODY))

    client.decide(decision_request)

    assert json.loads(sent[0].content) == {
        "model": "test/decision-model",
        # input에 객체를 그대로 넣으면 400
        "input": [{
            "type": "message", "role": "user",
            "content": [{"type": "input_json", "data": {"product_name": "색연필 24색 세트", "for_children": False}}],
        }],
        "questions": [
            {"type": "predicate", "name": "kind_kids", "instructions": "어린이가 주로 쓰는 종류인가"},
            {
                "type": "choice", "name": "category", "instructions": "상품 종류",
                "choices": [{"value": "stationery", "description": "학용품·문구"}, {"value": "other"}],
            },
            {
                "type": "score", "name": "kid_use", "instructions": "어린이가 쓰는 정도",
                "levels": [{"label": "low", "description": "거의 없음"}, {"label": "mid"}, {"label": "high"}],
            },
        ],
    }


def test_답과_토큰을_공통_응답으로_바꾼다(wire, client, decision_request):
    wire(client, lambda request: httpx.Response(200, json=LUNA_BODY))

    response = client.decide(decision_request)

    assert response.model == "gpt-6-luna"
    assert response.answers == {
        "kind_kids": YesNoAnswer(probability=0.94),
        "category": ChoiceAnswer(choice="stationery", probabilities={"stationery": 1.0, "other": 0.0}, confidence=1.0),
        # 응답 순서와 상관없이 단계 번호 순 리스트
        "kid_use": ScoreAnswer(score=0.86, probabilities=[0.34, 0.46, 0.2], confidence=0.19),
    }
    assert (response.input_tokens, response.cached_tokens, response.cache_write_tokens, response.output_tokens) == (
        419, 100, 20, 0)


def test_질문_단위_거부는_거부_답으로_바꾼다(wire, client, decision_request):
    answers = [{"type": "refusal", "name": "kind_kids"}, *LUNA_BODY["answers"][1:]]
    wire(client, lambda request: httpx.Response(200, json={**LUNA_BODY, "answers": answers}))

    response = client.decide(decision_request)

    assert response.answers["kind_kids"] == RefusedAnswer()
    assert response.answers["category"].type == "choice"


def test_모르는_답_종류는_DecisionResponseError(wire, client, decision_request):
    answers = [{"type": "box", "name": "kind_kids"}, *LUNA_BODY["answers"][1:]]
    wire(client, lambda request: httpx.Response(200, json={**LUNA_BODY, "answers": answers}))

    with pytest.raises(DecisionResponseError, match="box"):
        client.decide(decision_request)


@pytest.mark.parametrize("change", [
    {"answers": {"kind_kids": {"type": "predicate", "probability": 0.5}}},
    {"usage": None},
], ids=["답이 배열 아님", "사용량 null"])
def test_모양이_다른_응답도_DecisionResponseError(wire, client, decision_request, change):
    wire(client, lambda request: httpx.Response(200, json={**LUNA_BODY, **change}))

    with pytest.raises(DecisionResponseError):
        client.decide(decision_request)
