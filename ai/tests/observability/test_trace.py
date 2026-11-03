"""진단 trace 기록기: 꺼짐 무동작, 단계 중첩·ID, 실패 시 부분 기록, 값 변환을 확인한다."""

import json
from dataclasses import dataclass
from enum import Enum

import pytest
from pydantic import BaseModel

from app.observability.trace import current_trace, to_jsonable, trace_note, trace_run, trace_step


class _Color(Enum):
    RED = "red"


class _Item(BaseModel):
    name: str
    color: _Color


@dataclass
class _Pair:
    left: int
    right: _Color


def _read(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_기록_중이_아니면_단계와_값을_남기지_않는다():
    assert current_trace() is None
    with trace_step("extraction") as node:
        trace_note("kept", 1)
    assert node is None


def test_단계는_열린_순서대로_ID가_붙고_안쪽_단계는_바깥_단계_아래로_들어간다(tmp_path):
    with trace_run(tmp_path) as recorder:
        with trace_step("extraction", input="source"):
            trace_note("kept", 3)
        with trace_step("tool", tool="kc"):
            with trace_step("facts"):
                trace_note("dropped", ["a"])

    assert recorder.steps == [
        {"id": "s1", "kind": "extraction", "input": "source", "kept": 3},
        {"id": "s2", "kind": "tool", "tool": "kc", "steps": [{"id": "s3", "kind": "facts", "dropped": ["a"]}]},
    ]
    assert current_trace() is None


def test_끝나면_run_파일을_쓰고_열린_단계_밖의_값은_실행_정보로_남긴다(tmp_path):
    with trace_run(tmp_path, "run-2") as recorder:
        trace_note("source", "input.json")
        recorder.finish = {"reason": "completed"}

    assert _read(tmp_path / "run-2.json") == {
        "run": "run-2", "info": {"source": "input.json"}, "steps": [], "finish": {"reason": "completed"},
        "prompts": {},
    }
    assert [path.name for path in tmp_path.iterdir()] == ["run-2.json"]


def test_실패로_빠져나가도_거기까지_기록과_실패_단계를_남긴다(tmp_path):
    with pytest.raises(ValueError):
        with trace_run(tmp_path):
            with trace_step("selection"):
                raise ValueError("boom")

    saved = _read(tmp_path / "run-1.json")
    assert saved["steps"] == [{"id": "s1", "kind": "selection", "error": "ValueError"}]
    assert saved["finish"] == {"reason": "error", "error": "ValueError"}


def test_모델·dataclass·Enum·집합을_JSON_값으로_바꾸고_집합은_정렬한다():
    value = {"pair": _Pair(1, _Color.RED), "tags": {"b", "a"}, "items": (_Item(name="x", color=_Color.RED),)}

    assert to_jsonable(value) == {
        "pair": {"left": 1, "right": "red"}, "tags": ["a", "b"], "items": [{"name": "x", "color": "red"}],
    }


def test_파일을_못_써도_블록_안의_결과와_예외는_그대로다(tmp_path):
    blocked = tmp_path / "file"
    blocked.write_text("폴더 자리에 파일", encoding="utf-8")

    with trace_run(blocked / "run") as recorder:
        result = "진단 결과"
    with pytest.raises(ValueError, match="boom"):
        with trace_run(blocked / "run"):
            raise ValueError("boom")

    assert result == "진단 결과"
    assert recorder.save() is None
