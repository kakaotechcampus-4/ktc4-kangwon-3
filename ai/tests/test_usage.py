"""토큰 사용량 변환·기록·집계를 외부 API 없이 검증한다."""

import json
from types import SimpleNamespace

from app import usage
from app.schemas.clients.decision_response import DecisionUsage


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
    
def test_직렬화할_수_없는_값이_와도_기록이_남고_예외가_새지_않는다(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from uuid import UUID

    target = tmp_path / "usage.jsonl"
    monkeypatch.setattr(usage, "USAGE_LOG", target)
    call = usage.CallUsage("gpt-4.1-mini", 10, 0, 5)

    # 파이프라인이 문자열 대신 UUID·datetime을 넘기는 상황을 가정한다.
    usage.record(
        "verification",
        call,
        configured_model="openai/gpt-4.1-mini",
        subject_id=UUID("00000000-0000-0000-0000-000000000001"),
        elapsed_ms=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )

    row = json.loads(target.read_text(encoding="utf-8").splitlines()[0])
    assert row["subject_id"] == "00000000-0000-0000-0000-000000000001"
    assert row["total_tokens"] == 15


def test_로그_기록이_실패해도_예외를_밖으로_내지_않는다(tmp_path, monkeypatch):
    # 디렉터리를 파일 경로로 지정해 쓰기를 실패시킨다.
    target = tmp_path / "blocked"
    target.mkdir()
    monkeypatch.setattr(usage, "USAGE_LOG", target / "usage.jsonl" / "nested.jsonl")

    usage.record("verification", None)  # 예외가 새면 여기서 실패한다

def test_구조화_출력_원본에서_사용량을_뽑는다():
    # include_raw=True로 받은 응답에는 usage_metadata가 붙어 있다.
    raw = SimpleNamespace(
        usage_metadata={
            "input_tokens": 4000,
            "output_tokens": 500,
            "input_token_details": {"cache_read": 2200},
        },
        response_metadata={"model_name": "openai/gpt-4.1-mini"},
    )

    result = usage.from_response(raw)

    assert result.reported_model == "openai/gpt-4.1-mini"
    assert result.input_tokens == 4000
    assert result.cached_tokens == 2200
    assert result.output_tokens == 500
    # 캐시 적중분은 input에 포함된 값이라 단가가 다른 나머지를 따로 센다.
    assert result.uncached_input == 1800


def test_사용량이_없는_응답은_None이다():
    # 테스트 스텁처럼 실제 호출이 없었던 경우다.
    assert usage.from_response(SimpleNamespace()) is None
    assert usage.from_response(SimpleNamespace(usage_metadata={})) is None


def test_추론_토큰과_추론_강도를_함께_남긴다(tmp_path, monkeypatch):
    # 추론 토큰은 출력 토큰 안에 포함되어 보고됨. 비용은 출력으로 계산하고 강도별 비교용으로 따로 남김
    target = tmp_path / "usage.jsonl"
    monkeypatch.setattr(usage, "USAGE_LOG", target)
    raw = SimpleNamespace(
        usage_metadata={"input_tokens": 69, "output_tokens": 44, "output_token_details": {"reasoning": 17}},
        response_metadata={"model_name": "gpt-6-luna"},
    )
    handler = SimpleNamespace(usage_metadata={"gpt-6-luna": {
        "input_tokens": 1, "output_tokens": 30, "output_token_details": {"reasoning": 20}}})

    call = usage.from_response(raw)
    usage.record("extraction", call, configured_model="openai/gpt-6-luna", reasoning_effort="low")
    row = json.loads(target.read_text(encoding="utf-8"))

    assert (call.output_tokens, call.reasoning_tokens) == (44, 17)
    assert usage.from_handler(handler).reasoning_tokens == 20
    assert (row["reasoning_effort"], row["reasoning_tokens"]) == ("low", 17)



def test_LangChain이_놓친_Claude_캐시_토큰은_게이트웨이_원본_사용량에서_읽는다():
    # Claude는 캐시를 공통 필드로만 보내 usage_metadata의 input_token_details가 빔 (2026-10-14 실호출)
    raw = SimpleNamespace(
        usage_metadata={"input_tokens": 6468, "output_tokens": 33, "input_token_details": {}},
        response_metadata={"model_name": "claude-haiku-4-5", "token_usage": {
            "prompt_tokens": 6468, "cached_prompt_tokens": 6446, "cache_write_tokens": 0}},
    )
    first = SimpleNamespace(
        usage_metadata={"input_tokens": 8080, "output_tokens": 33, "input_token_details": {}},
        response_metadata={"token_usage": {"cached_prompt_tokens": 0, "cache_write_tokens": 6434}},
    )

    assert usage.from_response(raw).cached_tokens == 6446
    assert usage.from_response(first).cache_write_tokens == 6434


def test_OpenAI_형식_캐시_쓰기_토큰도_읽는다():
    raw = SimpleNamespace(
        usage_metadata={"input_tokens": 4285, "output_tokens": 53,
                        "input_token_details": {"cache_read": 0, "cache_creation": 3425},
                        "output_token_details": {"reasoning": 36}},
        response_metadata={"model_name": "gpt-6-luna"},
    )

    call = usage.from_response(raw)

    assert (call.cached_tokens, call.cache_write_tokens, call.reasoning_tokens) == (0, 3425, 36)


def test_호출과_집계에_캐시_적중률을_남긴다(tmp_path, monkeypatch):
    target = tmp_path / "usage.jsonl"
    monkeypatch.setattr(usage, "USAGE_LOG", target)
    usage.record("extraction", usage.CallUsage("m", 1000, 750, 10, reasoning_tokens=4, cache_write_tokens=0))
    usage.record("extraction", usage.CallUsage("m", 1000, 0, 10, cache_write_tokens=800))
    usage.record("selection", usage.CallUsage("m", 0, 0, 0))

    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    totals = usage.summarize(target)

    assert [row["cache_hit_rate"] for row in rows] == [0.75, 0.0, None]
    assert rows[1]["cache_write_tokens"] == 800
    assert (totals["cache_hit_rate"], totals["cache_write"], totals["reasoning"]) == (0.375, 800, 4)
    assert totals["by_agent"]["extraction"]["cache_hit_rate"] == 0.375
    assert totals["by_agent"]["selection"]["cache_hit_rate"] is None


def test_실패를_단계별로_기록하고_집계한다(tmp_path, monkeypatch):
    target = tmp_path / "usage.jsonl"
    monkeypatch.setattr(usage, "USAGE_LOG", target)
    usage.record("image_triage", usage.CallUsage("m", 10, 0, 1))
    usage.record("image_triage", usage.CallUsage("m", 10, 0, 1), ok=False, error_type="ImageTriageFailedError",
                 failure_phase="finalize")
    usage.record("extraction", None, ok=False, error_type="TimeoutError", failure_phase="call")
    # 단계 필드가 없던 옛 기록의 실패
    usage.record("electrical-facts", None, ok=False, error_type="ValueError")

    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    totals = usage.summarize(target)

    assert [row["failure_phase"] for row in rows] == [None, "finalize", "call", None]
    assert totals["failed"] == 3
    assert totals["failed_by_phase"] == {"finalize": 1, "call": 1, "unknown": 1}
    assert totals["by_agent"]["image_triage"]["failed_by_phase"] == {"finalize": 1}
    assert (totals["by_agent"]["image_triage"]["calls"], totals["by_agent"]["image_triage"]["failed"]) == (2, 1)


def test_LangChain이_사용량을_놓쳐도_게이트웨이_최종_사용량으로_남긴다():
    # Gemini는 조각마다 누적 사용량을 보내 usage_metadata가 None이 됨 (2026-10-14 실호출)
    raw = SimpleNamespace(
        usage_metadata=None,
        response_metadata={"model_name": "gemini-2.5-flash", "token_usage": {
            "prompt_tokens": 1963, "completion_tokens": 1773, "prompt_tokens_details": None,
            "completion_tokens_details": {"reasoning_tokens": 902}, "cached_prompt_tokens": 0, "cache_write_tokens": 0}},
    )

    call = usage.from_response(raw)

    assert (call.input_tokens, call.output_tokens, call.reasoning_tokens, call.cached_tokens) == (1963, 1773, 902, 0)


def test_게이트웨이_최종_사용량을_LangChain_값보다_먼저_쓴다():
    # OpenAI 형식 상세(prompt_tokens_details)가 있으면 그 값을 씀
    raw = SimpleNamespace(
        usage_metadata={"input_tokens": 1, "output_tokens": 1},
        response_metadata={"token_usage": {
            "prompt_tokens": 4285, "completion_tokens": 53,
            "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 3425},
            "completion_tokens_details": {"reasoning_tokens": 36}}},
    )

    call = usage.from_response(raw)

    assert (call.input_tokens, call.cache_write_tokens, call.reasoning_tokens) == (4285, 3425, 36)



def test_판단_응답에서_실제_모델과_토큰을_뽑는다():
    decision_usage = DecisionUsage(
        model="typesafe/jev-1.14-20261014", input_tokens=421, cached_tokens=100, cache_write_tokens=20,
    )

    call = usage.from_decision(decision_usage)

    assert call == usage.CallUsage(
        reported_model="typesafe/jev-1.14-20261014", input_tokens=421, cached_tokens=100, output_tokens=0,
        reasoning_tokens=0, cache_write_tokens=20,
    )


def test_판단_모델_비용은_요청한_등록명_단가로_계산한다():
    call = usage.CallUsage("typesafe/jev-1.14-20261014", input_tokens=1_000_000, cached_tokens=0, output_tokens=0)

    # 실제 버전이 아니라 요청한 등록명으로 단가를 찾음
    assert usage.estimate_krw(call, "typesafe/jev-latest") == 64.0
    assert usage.estimate_krw(call, "typesafe/jev-1.14-20261014") is None
