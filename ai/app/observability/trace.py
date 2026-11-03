"""로컬 진단 trace 기록기. 에이전트를 튜닝할 때 단계마다 무엇을 받아 무엇을 냈는지 JSON으로 남김.

서버에서는 켜지 않음. 로컬 CLI·평가가 trace_run()으로 감싼 블록에서만 기록하고, 밖에서는 아무것도 안 함.
지금 실행의 기록기는 문맥 변수로 찾음 → 단계·Tool 코드는 기록기를 넘겨받지 않아도 됨.

파일 구성 (실행 폴더 아래)
    - run-N.json: 단계(steps)와 결말(finish). 단계 안에 단계가 들어갈 수 있음
    - 그 밖: 단계 JSON에 다 넣기엔 큰 내용(모델 입출력 등)을 write_file()로 따로 쓰고 경로만 남김
ID는 실행 안에서 나온 순서대로 붙임(s1, s2, …). 같은 입력을 두 번 돌리면 같은 ID라 diff로 비교 가능.
"""

import dataclasses
import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    """JSON으로 쓸 수 있는 값으로 바꾼다. 모델·dataclass·Enum·집합도 받음.

    Args:
        value: 바꿀 값.

    Returns:
        Any: dict·list·str·int·float·bool·None으로만 된 값. 모르는 값은 repr 문자열.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(to_jsonable(key)): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        # 집합은 순서가 없어 정렬 (두 실행 diff 비교용)
        return sorted((to_jsonable(item) for item in value), key=lambda item: json.dumps(item, ensure_ascii=False))
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def _dump(data: Any) -> str:
    return json.dumps(to_jsonable(data), ensure_ascii=False, indent=2) + "\n"


class TraceRecorder:
    """실행 하나의 trace. 실행 스레드 하나만 씀.

    Attributes:
        directory: 실행 폴더. 같은 상품의 재진단 실행은 같은 폴더에 run-2.json, run-3.json으로 쌓음.
        run_name: 이 실행의 파일 이름(확장자 뺌).
        info: 실행 정보(입력 출처·모델 설정 등). run-N.json 맨 앞에 들어감.
        steps: 맨 바깥 단계. 실행 순서대로.
        finish: 결말. 실행이 끝날 때 채움.
    """

    def __init__(self, directory: Path, run_name: str = "run-1") -> None:
        self.directory = directory
        self.run_name = run_name
        self.info: dict[str, Any] = {}
        self.steps: list[dict[str, Any]] = []
        self.finish: dict[str, Any] | None = None
        self._open: list[dict[str, Any]] = []
        self._counters: dict[str, int] = {}

    def next_id(self, prefix: str) -> str:
        """접두어별로 1부터 차례로 ID를 붙인다.

        Args:
            prefix: ID 접두어 (단계 s, 모델 호출 c 등).

        Returns:
            str: 접두어 + 번호 (s1, s2, …).
        """
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}{self._counters[prefix]}"

    @contextmanager
    def step(self, kind: str, **fields: Any) -> Iterator[dict[str, Any]]:
        """단계 하나를 연다. 열린 단계 안에서 열면 그 단계의 하위 단계로 들어감.

        예외로 빠져나가면 예외 이름을 error로 남기고 그대로 다시 던짐.

        Args:
            kind: 단계 종류 (extraction, tool 등).
            **fields: 단계에 처음부터 넣을 값.

        Yields:
            dict[str, Any]: 단계 기록. 블록 안에서 값을 더 넣어도 됨.
        """
        node: dict[str, Any] = {"id": self.next_id("s"), "kind": kind}
        node.update(to_jsonable(fields))
        (self._open[-1].setdefault("steps", []) if self._open else self.steps).append(node)
        self._open.append(node)
        try:
            yield node
        except BaseException as exc:
            node["error"] = type(exc).__name__
            raise
        finally:
            self._open.pop()

    def current_step(self) -> dict[str, Any] | None:
        """지금 열린 가장 안쪽 단계. 없으면 None.

        Returns:
            dict[str, Any] | None: 단계 기록.
        """
        return self._open[-1] if self._open else None

    def note(self, key: str, value: Any) -> None:
        """지금 열린 단계에 값을 남긴다. 열린 단계가 없으면 실행 정보(info)에 남김.

        Args:
            key: 값 이름.
            value: 남길 값.
        """
        target = self._open[-1] if self._open else self.info
        target[key] = to_jsonable(value)

    def write_file(self, relative: str, data: Any) -> str:
        """실행 폴더 아래에 JSON 파일을 따로 쓴다.

        Args:
            relative: 실행 폴더 기준 경로 (calls/c1.json 등).
            data: 쓸 값.

        Returns:
            str: 실행 폴더 기준 경로. 단계 기록에 참조로 넣음.
        """
        path = self.directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump(data), encoding="utf-8")
        return relative

    def write_bytes(self, relative: str, data: bytes) -> str:
        """실행 폴더 아래에 바이너리 파일(이미지 등)을 쓴다.

        Args:
            relative: 실행 폴더 기준 경로.
            data: 쓸 내용.

        Returns:
            str: 실행 폴더 기준 경로.
        """
        path = self.directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return relative

    def to_dict(self) -> dict[str, Any]:
        """run-N.json에 쓸 내용.

        Returns:
            dict[str, Any]: 실행 정보·단계·결말.
        """
        return {"run": self.run_name, "info": self.info, "steps": self.steps, "finish": self.finish}

    def save(self) -> Path:
        """run-N.json을 쓴다. 이미 있으면 덮어씀.

        Returns:
            Path: 쓴 파일 경로.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{self.run_name}.json"
        path.write_text(_dump(self.to_dict()), encoding="utf-8")
        return path


_trace: ContextVar[TraceRecorder | None] = ContextVar("trace", default=None)


@contextmanager
def trace_run(directory: Path, run_name: str = "run-1") -> Iterator[TraceRecorder]:
    """이 블록의 실행을 새 trace에 기록하고, 끝나면 run-N.json을 쓴다.

    실패로 빠져나가도 거기까지 기록을 씀. 결말을 안 채웠으면 실패 예외 이름을 결말로 남김.

    Args:
        directory: 실행 폴더.
        run_name: 이 실행의 파일 이름(확장자 뺌).

    Yields:
        TraceRecorder: 이 실행의 기록기.
    """
    recorder = TraceRecorder(directory, run_name)
    token = _trace.set(recorder)
    try:
        yield recorder
    except BaseException as exc:
        if recorder.finish is None:
            recorder.finish = {"reason": "error", "error": type(exc).__name__}
        raise
    finally:
        _trace.reset(token)
        recorder.save()


def current_trace() -> TraceRecorder | None:
    """지금 실행의 기록기. trace_run() 밖이면 None.

    Returns:
        TraceRecorder | None: 기록기.
    """
    return _trace.get()


@contextmanager
def trace_step(kind: str, **fields: Any) -> Iterator[dict[str, Any] | None]:
    """기록 중이면 단계 하나를 연다. 기록 중이 아니면 아무것도 안 함.

    Args:
        kind: 단계 종류.
        **fields: 단계에 처음부터 넣을 값.

    Yields:
        dict[str, Any] | None: 단계 기록. 기록 중이 아니면 None.
    """
    recorder = _trace.get()
    if recorder is None:
        yield None
        return
    with recorder.step(kind, **fields) as node:
        yield node


def trace_note(key: str, value: Any) -> None:
    """기록 중이면 지금 열린 단계에 값을 남긴다. 기록 중이 아니면 아무것도 안 함.

    Args:
        key: 값 이름.
        value: 남길 값.
    """
    recorder = _trace.get()
    if recorder is not None:
        recorder.note(key, value)
