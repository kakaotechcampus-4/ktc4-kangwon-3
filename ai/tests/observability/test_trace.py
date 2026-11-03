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
    }


def test_실패로_빠져나가도_거기까지_기록과_실패_단계를_남긴다(tmp_path):
    with pytest.raises(ValueError):
        with trace_run(tmp_path):
            with trace_step("selection"):
                raise ValueError("boom")

    saved = _read(tmp_path / "run-1.json")
    assert saved["steps"] == [{"id": "s1", "kind": "selection", "error": "ValueError"}]
    assert saved["finish"] == {"reason": "error", "error": "ValueError"}


def test_큰_내용은_따로_파일로_쓰고_경로를_돌려준다(tmp_path):
    with trace_run(tmp_path) as recorder:
        path = recorder.write_file("calls/c1.json", {"output": _Item(name="램프", color=_Color.RED)})
        image = recorder.write_bytes("images/i1.png", b"\x89PNG")

    assert path == "calls/c1.json"
    assert _read(tmp_path / path) == {"output": {"name": "램프", "color": "red"}}
    assert (tmp_path / image).read_bytes() == b"\x89PNG"


def test_모델·dataclass·Enum·집합을_JSON_값으로_바꾸고_집합은_정렬한다():
    value = {"pair": _Pair(1, _Color.RED), "tags": {"b", "a"}, "items": (_Item(name="x", color=_Color.RED),)}

    assert to_jsonable(value) == {
        "pair": {"left": 1, "right": "red"}, "tags": ["a", "b"], "items": [{"name": "x", "color": "red"}],
    }
