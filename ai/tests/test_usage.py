"""토큰 사용량 변환·기록·집계를 외부 API 없이 검증한다."""

import json
from types import SimpleNamespace

from app import usage


def test_handler_사용량을_합산하고_캐시_입력을_분리한다():
    handler = SimpleNamespace(
        usage_metadata={
            "gpt-a": {
                "input_tokens": 100,
                "output_tokens": 20,
                "input_token_details": {"cache_read": 40},
            },
            "gpt-b": {
                "input_tokens": 50,
                "output_tokens": 10,
                "input_token_details": {},
            },
        }
    )

    result = usage.from_handler(handler)

    assert result.reported_model == "gpt-a, gpt-b"
    assert result.input_tokens == 150
    assert result.cached_tokens == 40
    assert result.output_tokens == 30
    assert result.total_tokens == 180


def test_JSONL을_기록하고_에이전트별로_집계한다(tmp_path, monkeypatch):
    target = tmp_path / "usage.jsonl"
    monkeypatch.setattr(usage, "USAGE_LOG", target)
    call = usage.CallUsage("gpt-4.1-mini", 1000, 200, 100)

    usage.record(
        "verification",
        call,
        configured_model="openai/gpt-4.1-mini",
        subject_id="p1",
        elapsed_ms=12,
    )
    # 깨진 한 줄이 있어도 앞의 정상 기록은 집계한다.
    with target.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")

    row = json.loads(target.read_text(encoding="utf-8").splitlines()[0])
    totals = usage.summarize(target)

    assert row["subject_id"] == "p1"
    assert row["total_tokens"] == 1100
    assert row["estimated_cost_krw"] is not None
    assert totals["calls"] == 1
    assert totals["input"] == 1000
    assert totals["cached"] == 200
    assert totals["output"] == 100
    assert totals["by_agent"]["verification"]["calls"] == 1
