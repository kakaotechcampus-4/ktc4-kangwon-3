"""호출 1건의 사용량 기록(record_call)과 콘솔 토큰 로그(log_token_usage)."""

import logging

from langchain_core.messages import AIMessage

from app.agents.base import AgentRunMeta
from app.agents.base.usage_log import log_token_usage, record_call
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


def test_콘솔_로그에_토큰·캐시_적중률을_남기고_게이트웨이_원본은_디버그로_남긴다(caplog):
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

    monkeypatch.setattr("app.agents.base.usage_log.logger.info", broken)

    log_token_usage("fake", _USAGE, None)
