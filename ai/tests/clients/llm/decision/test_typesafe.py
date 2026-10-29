"""Jev(TypeSafe) 판단 클라이언트가 공통 요청을 TypeSafe 본문으로, TypeSafe 응답을 공통 응답으로 바꾸는지 확인한다.

응답 본문은 2026-10-29 실제 Jev 응답 모양. 실제 네트워크 요청은 보내지 않는다.
"""

import json

import httpx
import pytest

from app.clients.llm.decision import DecisionResponseError
from app.clients.llm.decision.typesafe import TypeSafeDecisionClient
from app.schemas.clients.decision_response import ChoiceAnswer, ScoreAnswer, YesNoAnswer

from .conftest import API_KEY, BASE_URL

JEV_BODY = {
    "model": "typesafe/jev-1.14-20261014",
    "answers": {
        "kind_kids": {"type": "noul", "noul": 0.61},
        "category": {
            "type": "choice", "choice": "stationery",
            "probabilities": {"stationery": 0.99, "other": 0.01}, "confidence": 0.98,
        },
        "kid_use": {
            "type": "score", "score": 0.19,
            "legend": {"0": "low: 거의 없음", "1": "mid", "2": "high"},
            "probabilities": {"2": 0.05, "0": 0.86, "1": 0.09}, "confidence": 0.71,
        },
    },
    "usage": {
        "prompt_tokens": 421, "completion_tokens": 0, "input_tokens": 421, "output_tokens": 0,
        "cached_prompt_tokens": 100, "cache_write_tokens": 20,
        "completion_tokens_details": {"unbilled_output_tokens": 60},
    },
    "id": "gen-dec-1", "provider": "TypeSafe",
}


@pytest.fixture
def client() -> TypeSafeDecisionClient:
    return TypeSafeDecisionClient(BASE_URL, API_KEY)


def test_판단_대상은_state에_질문은_이름_키_맵으로_보낸다(wire, client, decision_request):
    sent = wire(client, lambda request: httpx.Response(200, json=JEV_BODY))

    client.decide(decision_request)

    assert json.loads(sent[0].content) == {
        "model": "test/decision-model",
        "state": {"product_name": "색연필 24색 세트", "for_children": False},
        "questions": {
            "kind_kids": {"type": "noul", "instructions": "어린이가 주로 쓰는 종류인가"},
            "category": {
                "type": "choice", "instructions": "상품 종류",
                "criteria": {"stationery": "학용품·문구", "other": None},
            },
            # 단계마다 문자열 하나만 받아 이름과 설명을 합침
            "kid_use": {"type": "score", "instructions": "어린이가 쓰는 정도", "criteria": ["low: 거의 없음", "mid", "high"]},
        },
    }


def test_답과_토큰을_공통_응답으로_바꾼다(wire, client, decision_request):
    wire(client, lambda request: httpx.Response(200, json=JEV_BODY))

    response = client.decide(decision_request)

    assert response.model == "typesafe/jev-1.14-20261014"
    assert response.answers == {
        "kind_kids": YesNoAnswer(probability=0.61),
        "category": ChoiceAnswer(
            choice="stationery", probabilities={"stationery": 0.99, "other": 0.01}, confidence=0.98,
        ),
        # 단계 번호 키 순서와 상관없이 번호 순 리스트
        "kid_use": ScoreAnswer(score=0.19, probabilities=[0.86, 0.09, 0.05], confidence=0.71),
    }
    assert (response.input_tokens, response.cached_tokens, response.cache_write_tokens, response.output_tokens) == (
        421, 100, 20, 0)


def test_모르는_답_종류는_DecisionResponseError(wire, client, decision_request):
    body = {**JEV_BODY, "answers": {**JEV_BODY["answers"], "kind_kids": {"type": "box", "box": [0, 0, 1, 1]}}}
    wire(client, lambda request: httpx.Response(200, json=body))

    with pytest.raises(DecisionResponseError, match="box"):
        client.decide(decision_request)


@pytest.mark.parametrize("change", [
    {"answers": [{"type": "noul", "noul": 0.5}]},
    {"usage": None},
], ids=["답이 맵 아님", "사용량 null"])
def test_모양이_다른_응답도_DecisionResponseError(wire, client, decision_request, change):
    wire(client, lambda request: httpx.Response(200, json={**JEV_BODY, **change}))

    with pytest.raises(DecisionResponseError):
        client.decide(decision_request)
