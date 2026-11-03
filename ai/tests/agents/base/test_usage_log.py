"""호출 1건의 사용량 기록(record_call), 호출 로그(log_call), 토큰 디버그 로그(log_token_usage)."""

import logging

from langchain_core.messages import AIMessage

from app.agents.base import AgentRunMeta
from app.agents.base.usage_log import log_call, log_token_usage, record_call
from app.observability.agent_sinks import agent_sinks
from app.usage import CallUsage

_USAGE = CallUsage("openai/gpt-4.1-mini", input_tokens=100, cached_tokens=40, output_tokens=20)


def test_성공·실패_여부는_오류_타입으로_정해진다(records):
    record_call(AgentRunMeta(component="fake", model="m", usage=_USAGE, elapsed_ms=5), "p-1")
    record_call(AgentRunMeta(component="fake", model="m", elapsed_ms=5, error_type="TimeoutError"), "p-1")

    assert [(row["ok"], row["error_type"]) for row in records] == [(True, None), (False, "TimeoutError")]
    assert (records[0]["usage"], records[1]["usage"]) == (_USAGE, None)


def test_기록은_app_usage_record를_거친다(records):
    # 테스트·평가 러너(전기 Tool)가 이 이름을 바꿔치기해 사용량을 캡처함
    record_call(AgentRunMeta(component="fake", model="m", usage=_USAGE), "p-1")

    assert [row["agent"] for row in records] == ["fake"]


def test_기록_이름이_있으면_에이전트_이름_대신_쓴다(records):
    # 평가 호출(extraction-eval 등)이 운영 사용량과 섞이지 않게
    record_call(AgentRunMeta(component="fake", usage_name="fake-eval", usage=_USAGE), "p-1")

    assert [row["agent"] for row in records] == ["fake-eval"]


def test_사용량_로그_sink는_기본으로_등록돼_있다(records):
    agent_sinks.publish(AgentRunMeta(component="fake", usage=_USAGE), "p-1")

    assert [(row["agent"], row["subject_id"]) for row in records] == [("fake", "p-1")]


def test_토큰·캐시_적중률과_게이트웨이_원본은_디버그로_남긴다(caplog):
    raw = AIMessage(content="", response_metadata={"token_usage": {"prompt_tokens": 100}})

    with caplog.at_level(logging.DEBUG, logger="app.agents.base.usage_log"):
        log_token_usage("fake", _USAGE, raw)

    assert "fake 토큰 사용량 input=100 (cache_read=40" in caplog.text
    assert "적중률 40.0%" in caplog.text
    assert "게이트웨이 원본 usage" in caplog.text


def test_사용량이_없으면_로그를_남기지_않는다(caplog):
    with caplog.at_level(logging.DEBUG, logger="app.agents.base.usage_log"):
        log_token_usage("fake", None, None)

    assert caplog.text == ""


def test_콘솔_로그가_실패해도_예외를_내지_않는다(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("로그 핸들러 오류")

    monkeypatch.setattr("app.agents.base.usage_log.logger.debug", broken)

    log_token_usage("fake", _USAGE, None)


def test_호출마다_모델·시간·토큰·비용을_INFO_한_줄로_남긴다(caplog):
    meta = AgentRunMeta(component="extraction", model="gpt-x", usage=_USAGE, cost_krw=12.345, elapsed_ms=1500)

    with caplog.at_level(logging.INFO, logger="app.agents.base.usage_log"):
        log_call(meta, "p-1")

    assert [(r.levelname, r.getMessage()) for r in caplog.records] == [
        ("INFO", "모델 호출 extraction (모델 gpt-x, 1500ms, 토큰 입력 100(캐시 40) 출력 20(추론 0), 12.3원)"),
    ]


def test_실패한_호출은_실패_단계와_원인과_함께_경고로_남긴다(caplog):
    meta = AgentRunMeta(component="verification", model="gpt-x", elapsed_ms=30000, error_type="TimeoutError",
                        failure_phase="call")

    log_call(meta, "p-1")

    assert [(r.levelname, r.getMessage()) for r in caplog.records] == [
        ("WARNING", "모델 호출 실패 verification (모델 gpt-x, 30000ms, call 단계 TimeoutError)"),
    ]


def test_호출_로그_sink는_기본으로_등록돼_있다(records, caplog):
    with caplog.at_level(logging.INFO, logger="app.agents.base.usage_log"):
        agent_sinks.publish(AgentRunMeta(component="fake", usage=_USAGE), "p-1")

    assert any(r.getMessage().startswith("모델 호출 fake") for r in caplog.records)
