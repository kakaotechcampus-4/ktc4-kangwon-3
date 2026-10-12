"""AnnexParsingAgent 동작 검증. 실제 모델 호출 없이 스텁·가짜 게이트웨이로 대체한다."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from openai.lib._parsing._completions import type_to_response_format_param

from app import usage
from app.agents.annex_parsing import AnnexParsingAgent, AnnexParsingError
from app.agents.base import AgentError
from app.schemas.agents.annex import AnnexParseOutput, AnnexSource
from app.utils.annex_check import source_labels
from app.utils.annex_text import compact_annex, split_annex

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "annex"
_SMALL_DIR = _FIXTURES / "전기용품및생활용품안전관리운용요령_별표0003-02"
_RADIO_DIR = _FIXTURES / "방송통신기자재등의적합성평가에관한고시_별표0001-00"


def _load(directory: Path) -> tuple[AnnexSource, str]:
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    return AnnexSource.model_validate(meta["source"]), (directory / "content.txt").read_text(encoding="utf-8")


def _item(label: str, category: str, name: str, source_text: str, conditions: list[str]) -> dict:
    return {
        "category_path": ["1. 재사용전지", category],
        "item_label": label,
        "item_name": name,
        "conditions": conditions,
        "exclusions": [],
        "inclusions": ["교류전원 30V 이하, 직류전원 42V 이하에서 사용하는 것을 포함한다."],
        "attributes": [],
        "source_text": source_text,
    }


# 운용요령 별표 3의2 정답
_SMALL_OUTPUT = AnnexParseOutput.model_validate({
    "scheme": "안전성검사대상전기용품",
    "items": [
        _item("①", "① 재사용전지모듈", "재사용전지모듈", "① 재사용전지모듈", []),
        _item("②", "② 재사용전지시스템", "재사용전지시스템", "② 재사용전지시스템(정격용량이 300kWh 이하인 것만 해당한다)",
              ["정격용량이 300kWh 이하인 것만 해당한다"]),
    ],
    "skipped": [],
    "notes": [],
})

_EMPTY_OUTPUT = AnnexParseOutput(scheme="적합성평가 대상기자재", items=[], skipped=[], notes=[])
_FAKE_USAGE = {"input_tokens": 3000, "output_tokens": 400, "total_tokens": 3400}


class _StubChatModel:
    """조각마다 정해 둔 출력을 차례로 돌려주는 스텁. 받은 메시지를 쌓아 둔다."""

    def __init__(self, *results: AnnexParseOutput | Exception) -> None:
        self._results = list(results)
        self.received: list[list] = []
        self.structured_kwargs: dict | None = None

    def with_structured_output(self, schema: dict, **kwargs) -> "_StubChatModel":
        assert schema == type_to_response_format_param(AnnexParseOutput)["json_schema"]
        self.structured_kwargs = kwargs
        return self

    def invoke(self, messages: list) -> dict:
        self.received.append(messages)
        result = self._results.pop(0) if len(self._results) > 1 else self._results[0]
        if isinstance(result, Exception):
            raise result
        return {"raw": SimpleNamespace(usage_metadata=_FAKE_USAGE, response_metadata={}),
                "parsed": result, "parsing_error": None}


def _payload(messages: list) -> dict:
    return json.loads(messages[1].content)


def test_작은_별표는_한_번_호출하고_원문과_맞으면_검증을_통과한다():
    source, content = _load(_SMALL_DIR)
    model = _StubChatModel(_SMALL_OUTPUT)

    record = AnnexParsingAgent(model=model).parse(source, content)

    assert len(model.received) == 1
    assert record.verified is True
    assert record.failure_reasons == []
    assert record.output == _SMALL_OUTPUT
    assert record.source == source


def test_다듬은_조각과_출처를_JSON으로_넣고_strict_구조화_출력을_쓴다():
    source, content = _load(_SMALL_DIR)
    model = _StubChatModel(_SMALL_OUTPUT)

    AnnexParsingAgent(model=model).parse(source, content)

    system, human = model.received[0]
    assert "별표 파싱 에이전트" in system.content
    assert _payload(model.received[0]) == {
        "source": source.model_dump(mode="json"),
        "content": compact_annex(content),
        "context": "",
        "missing_labels": [],
    }
    assert model.structured_kwargs == {"include_raw": True, "method": "json_schema", "strict": True}


def test_원문과_다른_결과는_예외_없이_검증_실패와_사유로_남긴다():
    source, content = _load(_SMALL_DIR)
    paraphrased = _SMALL_OUTPUT.model_copy(update={"items": _SMALL_OUTPUT.items[:1]})

    record = AnnexParsingAgent(model=_StubChatModel(paraphrased)).parse(source, content)

    assert record.verified is False
    assert record.failure_reasons == ["번호 누락: {'②': 1}"]
    # 어느 행이 틀렸는지 볼 수 있게 출력은 남김
    assert record.output == paraphrased


def test_큰_별표는_조각마다_호출하고_순서대로_병합한다():
    source, content = _load(_RADIO_DIR)
    chunks = split_annex(compact_annex(content))
    outputs = [
        _EMPTY_OUTPUT.model_copy(update={"scheme": f"구분{index}", "notes": ["공통 비고", f"비고{index}"]})
        for index in range(len(chunks))
    ]
    # 빈 출력이라 번호가 있는 조각은 한 번씩 다시 부름. 다시 불러도 같은 출력
    rows = [sum(source_labels(chunk.content).values()) for chunk in chunks]
    model = _StubChatModel(*(output for output, count in zip(outputs, rows) for _ in range(2 if count else 1)))

    record = AnnexParsingAgent(model=model).parse(source, content)

    first_calls = [_payload(messages) for messages in model.received if not _payload(messages)["missing_labels"]]
    assert [payload["content"] for payload in first_calls] == [chunk.content for chunk in chunks]
    assert [payload["context"] for payload in first_calls] == [chunk.context for chunk in chunks]
    assert len(model.received) == len(chunks) + sum(1 for count in rows if count)
    assert record.output.scheme == "구분0"
    assert record.output.notes == ["공통 비고", *(f"비고{index}" for index in range(len(chunks)))]
    assert record.verified is False  # 빈 출력이라 번호 누락


def test_조각_호출이_실패하면_앞_조각까지_병합한_결과를_예외에_담는다():
    source, content = _load(_RADIO_DIR)
    first = _EMPTY_OUTPUT.model_copy(update={"notes": ["첫 조각"]})
    # 첫 조각은 번호가 빠져 한 번 다시 부르고, 둘째 조각 호출에서 실패
    model = _StubChatModel(first, first, RuntimeError("rate limit exceeded"))

    with pytest.raises(AnnexParsingError, match="별표 파싱 모델 호출에 실패했습니다") as caught:
        AnnexParsingAgent(model=model).parse(source, content)

    assert isinstance(caught.value, AgentError)
    assert caught.value.partial_result == first
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_스키마와_맞지_않는_응답은_파싱_실패로_감싼다(fake_gateway):
    source, content = _load(_SMALL_DIR)
    requests: list[dict] = []

    with pytest.raises(AnnexParsingError, match="AnnexParseOutput 스키마와 맞지 않습니다"):
        AnnexParsingAgent(model=fake_gateway('{"scheme": "x"}', "stop", requests)).parse(source, content)

    response_format = requests[0]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True


def test_호출마다_별표_단위_대상_ID로_사용량을_남긴다(monkeypatch):
    source, content = _load(_SMALL_DIR)
    recorded: list[dict] = []
    monkeypatch.setattr(usage, "record", lambda agent, call_usage, **kw: recorded.append({"agent": agent, **kw}))
    monkeypatch.setattr("app.agents.base.record", usage.record)

    AnnexParsingAgent(model=_StubChatModel(_SMALL_OUTPUT), usage_agent="annex-parsing-eval").parse(source, content)

    assert [(row["agent"], row["subject_id"], row["ok"]) for row in recorded] == [
        ("annex-parsing-eval", "2100000285148:별표0003-02", True),
    ]


def test_조각에서_번호가_빠지면_빠진_번호를_알려_주고_한_번_다시_부른다():
    source, content = _load(_SMALL_DIR)
    partial = _SMALL_OUTPUT.model_copy(update={"items": _SMALL_OUTPUT.items[:1]})
    model = _StubChatModel(partial, _SMALL_OUTPUT)

    record = AnnexParsingAgent(model=model).parse(source, content)

    assert [_payload(messages)["missing_labels"] for messages in model.received] == [[], ["②"]]
    assert record.verified is True
    assert record.output == _SMALL_OUTPUT


def test_다시_부른_결과가_더_빠뜨리면_처음_결과를_쓴다():
    source, content = _load(_SMALL_DIR)
    partial = _SMALL_OUTPUT.model_copy(update={"items": _SMALL_OUTPUT.items[:1]})
    worse = _SMALL_OUTPUT.model_copy(update={"items": []})
    model = _StubChatModel(partial, worse)

    record = AnnexParsingAgent(model=model).parse(source, content)

    assert len(model.received) == 2
    assert record.output == partial
    assert record.failure_reasons == ["번호 누락: {'②': 1}"]
