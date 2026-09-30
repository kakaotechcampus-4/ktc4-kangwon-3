"""usage.record()가 LLM 지표를 남기는지 실제 모델 호출 없이 검증한다."""

import pytest
from prometheus_client import REGISTRY

from app import usage
from app.usage import CallUsage, record

MODEL = "openai/gpt-4.1-mini"


def _value(name: str, labels: dict) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def _tokens(agent: str, token_type: str) -> float:
    return _value("ai_llm_tokens_total", {"agent": agent, "model": MODEL, "type": token_type})


def test_호출_1건이_요청_수_소요시간_토큰_비용에_반영된다():
    agent = "metrics-test-success"
    call = CallUsage(reported_model=MODEL, input_tokens=1000, cached_tokens=200, output_tokens=300)

    record(agent, call, configured_model=MODEL, ok=True, elapsed_ms=1500)

    assert _value("ai_llm_requests_total", {"agent": agent, "model": MODEL, "result": "success"}) == 1
    assert _value("ai_llm_request_duration_seconds_sum", {"agent": agent}) == pytest.approx(1.5)
    assert _tokens(agent, "uncached") == 800
    assert _tokens(agent, "cached") == 200
    assert _tokens(agent, "output") == 300
    assert _value("ai_llm_cost_krw_total", {"agent": agent, "model": MODEL}) == pytest.approx(
        usage.estimate_krw(call, MODEL)
    )


def test_실패한_호출은_error로_세고_토큰은_남기지_않는다():
    agent = "metrics-test-error"

    record(agent, None, configured_model=MODEL, ok=False, elapsed_ms=300, error_type="TimeoutError")

    assert _value("ai_llm_requests_total", {"agent": agent, "model": MODEL, "result": "error"}) == 1
    assert _tokens(agent, "uncached") == 0


def test_로그_파일_기록이_실패해도_지표는_남는다(monkeypatch, tmp_path):
    agent = "metrics-test-file-error"
    blocked = tmp_path / "blocked"
    blocked.write_text("")
    monkeypatch.setattr(usage, "USAGE_LOG", blocked / "usage.jsonl")

    record(agent, None, configured_model=MODEL, ok=True)

    assert _value("ai_llm_requests_total", {"agent": agent, "model": MODEL, "result": "success"}) == 1
