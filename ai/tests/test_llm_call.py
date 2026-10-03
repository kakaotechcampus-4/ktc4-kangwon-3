"""LLM 호출 측정 테스트. 실제 API 없이 가짜 응답과 가짜 모델로 기록 내용을 확인한다."""

import logging
from types import SimpleNamespace

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from app import llm_call

_USAGE = {
    "input_tokens": 4000,
    "output_tokens": 600,
    "total_tokens": 4600,
    "input_token_details": {"cache_read": 1500},
}


def _raw(usage_metadata=_USAGE):
    return SimpleNamespace(usage_metadata=usage_metadata, response_metadata={"model_name": "gpt-4.1-mini"})


@pytest.fixture
def records(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.usage.record",
        lambda name, measured, **kwargs: calls.append({"name": name, "usage": measured, **kwargs}),
    )
    return calls


def test_정상_호출은_토큰과_함께_성공으로_한_번_기록한다(records):
    with llm_call.track_llm_call("extraction", configured_model="openai/gpt-4.1-mini", subject_id="P001") as call:
        call.use_response(_raw())

    assert len(records) == 1
    entry = records[0]
    assert entry["name"] == "extraction"
    assert entry["ok"] is True
    assert entry["error_type"] is None
    assert entry["subject_id"] == "P001"
    assert entry["configured_model"] == "openai/gpt-4.1-mini"
    assert entry["usage"].input_tokens == 4000
    assert entry["usage"].cached_tokens == 1500
    assert entry["usage"].reported_model == "gpt-4.1-mini"
    assert isinstance(entry["elapsed_ms"], int)


def test_호출_실패는_예외_타입으로_기록하고_예외를_그대로_던진다(records):
    error = TimeoutError("timeout")

    with pytest.raises(TimeoutError) as raised:
        with llm_call.track_llm_call("selection"):
            raise error

    assert raised.value is error
    assert len(records) == 1
    assert records[0]["ok"] is False
    assert records[0]["error_type"] == "TimeoutError"
    assert records[0]["usage"] is None


def test_응답을_쓸_수_없으면_실패로_기록하되_토큰은_남긴다(records):
    with llm_call.track_llm_call("verification") as call:
        call.use_response(_raw())
        call.fail("OutputParserException")

    assert len(records) == 1
    assert records[0]["ok"] is False
    assert records[0]["error_type"] == "OutputParserException"
    assert records[0]["usage"].output_tokens == 600


def test_실패를_알린_뒤_예외가_나면_먼저_알린_원인을_남긴다(records):
    with pytest.raises(RuntimeError):
        with llm_call.track_llm_call("extraction") as call:
            call.fail("MissingParsedOutput")
            raise RuntimeError("wrapped")

    assert len(records) == 1
    assert records[0]["error_type"] == "MissingParsedOutput"


def test_원본_응답이_없으면_콜백이_모은_사용량을_쓴다(records):
    model = GenericFakeChatModel(
        messages=iter(
            [AIMessage(content="ok", usage_metadata=_USAGE, response_metadata={"model_name": "gpt-4.1-mini"})]
        )
    )

    with llm_call.track_llm_call("verification") as call:
        model.invoke("검증", config={"callbacks": call.callbacks})

    assert records[0]["usage"].input_tokens == 4000
    assert records[0]["usage"].reported_model == "gpt-4.1-mini"


def test_원본_응답에_사용량이_없으면_콜백_사용량으로_대체한다(records):
    model = GenericFakeChatModel(
        messages=iter(
            [AIMessage(content="ok", usage_metadata=_USAGE, response_metadata={"model_name": "gpt-4.1-mini"})]
        )
    )

    with llm_call.track_llm_call("selection") as call:
        model.invoke("선택", config={"callbacks": call.callbacks})
        call.use_response(SimpleNamespace(usage_metadata=None, response_metadata={}))

    assert records[0]["usage"].output_tokens == 600


def test_사용량을_알_수_없으면_토큰_없이_기록한다(records):
    with llm_call.track_llm_call("extraction"):
        pass

    assert records[0]["ok"] is True
    assert records[0]["usage"] is None


def test_토큰_로그는_넘긴_로거로_남긴다(records, caplog):
    logger = logging.getLogger("app.agents.extraction")

    with caplog.at_level(logging.INFO, logger="app.agents.extraction"):
        with llm_call.track_llm_call("extraction", logger=logger) as call:
            call.use_response(_raw())

    assert [r.name for r in caplog.records] == ["app.agents.extraction"]
    assert "input=4000 (cache_read=1500) output=600 total=4600" in caplog.text


def test_실제_기록_파일에도_한_줄이_남는다(tmp_path, monkeypatch):
    from app import usage

    log = tmp_path / "usage.jsonl"
    monkeypatch.setattr(usage, "USAGE_LOG", log)

    with llm_call.track_llm_call("extraction", configured_model="openai/gpt-4.1-mini") as call:
        call.use_response(_raw())

    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert '"input_tokens": 4000' in lines[0]
    assert '"success": true' in lines[0]
