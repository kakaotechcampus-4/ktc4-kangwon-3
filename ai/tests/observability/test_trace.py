"""진단 trace 기록기: 꺼짐 무동작, 단계 중첩·ID, 실패 시 부분 기록, 값 변환을 확인한다."""

import json
from dataclasses import dataclass
from enum import Enum

import pytest
from pydantic import BaseModel

from app.observability.trace import (
    current_trace, error_info, to_jsonable, trace_alias, trace_note, trace_run, trace_step,
)


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
    assert saved["steps"] == [{"id": "s1", "kind": "selection", "error": {"type": "ValueError", "message": "boom"}}]
    assert saved["finish"] == {
        "reason": "error", "error": {"type": "ValueError", "message": "boom"},
        "at": {"step": "s1", "kind": "selection", "path": ["s1"], "call": None},
    }


def test_감싸서_다시_던진_예외는_바깥_단계엔_처음_실패한_단계만_가리키고_결말엔_원인까지_남긴다(tmp_path):
    with pytest.raises(RuntimeError):
        with trace_run(tmp_path):
            with trace_step("rounds"):
                try:
                    with trace_step("verification"):
                        raise KeyError("finding-1")
                except KeyError as exc:
                    raise RuntimeError("검증 실패") from exc

    saved = _read(tmp_path / "run-1.json")
    [rounds] = saved["steps"]
    assert rounds["steps"][0]["error"] == {"type": "KeyError", "message": "'finding-1'"}
    assert rounds["error"] == {"type": "RuntimeError", "from": "s2"}
    assert saved["finish"]["error"] == {"type": "RuntimeError", "message": "검증 실패",
                                        "cause": {"type": "KeyError", "message": "'finding-1'"}}
    assert saved["finish"]["at"] == {"step": "s2", "kind": "verification", "path": ["s1", "s2"], "call": None}


def test_잡힌_실패_뒤의_다른_실패는_새_위치로_남긴다(tmp_path):
    with pytest.raises(TypeError):
        with trace_run(tmp_path) as recorder:
            with pytest.raises(ValueError):
                with trace_step("tool"):
                    raise ValueError("Tool 실패")
            with trace_step("aggregation"):
                raise TypeError("집계 실패")

    assert recorder.finish["at"]["step"] == "s2"


def test_실패를_처리하다_난_다른_실패는_앞_실패에_묶지_않는다(tmp_path):
    with pytest.raises(TypeError):
        with trace_run(tmp_path) as recorder:
            try:
                with trace_step("tool"):
                    raise ValueError("Tool 실패")
            except ValueError:
                with trace_step("fallback"):
                    raise TypeError("대체 처리 실패")

    fallback = recorder.steps[1]
    assert fallback["error"] == {"type": "TypeError", "message": "대체 처리 실패"}
    assert recorder.finish["at"]["step"] == "s2"


def test_실행마다_달라지는_값은_처음_나온_순서대로_번호를_붙이고_기록_중이_아니면_그대로다(tmp_path):
    assert trace_alias("uuid-a", "f") == "uuid-a"
    with trace_run(tmp_path):
        assert [trace_alias(value, "f") for value in ("uuid-a", "uuid-b", "uuid-a")] == ["f1", "f2", "f1"]
        trace_note("keys", {"uuid-b": "uuid-a 와 uuid-b"})

    assert _read(tmp_path / "run-1.json")["info"] == {"keys": {"f2": "f1 와 f2"}}


def test_이전_실행_값에_든_번호_다음부터_세고_이전_번호와_단계·호출_번호는_그대로다(tmp_path):
    earlier = json.dumps({"finding_id": "f3", "issue_id": "i2", "step": "s9", "text": "f7 언급"})

    with trace_run(tmp_path) as recorder:
        recorder.continue_ids(earlier)
        with trace_step("tool") as step:
            pass

        assert [trace_alias("uuid-a", "f"), trace_alias("uuid-b", "i"), trace_alias("uuid-c", "e")] == ["f4", "i3", "e1"]
        assert [trace_alias("f3", "f"), trace_alias("i2", "i")] == ["f3", "i2"]
    assert step["id"] == "s1"


def test_예외_메시지는_길면_자른다():
    assert len(error_info(ValueError("가" * 5000))["message"]) == 1000


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
