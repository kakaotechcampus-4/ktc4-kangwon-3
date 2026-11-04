"""로컬 진단 trace 기록기. 에이전트를 튜닝할 때 단계마다 무엇을 받아 무엇을 냈는지 JSON으로 남김.

서버에서는 켜지 않음. 로컬 CLI(diagnosis/trace_cli.py)가 trace_run()으로 감싼 블록에서만 기록하고, 밖에서는 아무것도 안 함.
지금 실행의 기록기는 문맥 변수로 찾음 → 단계·Tool 코드는 기록기를 넘겨받지 않아도 됨.

실행 하나 = 파일 하나 (실행 폴더/run-N.json). 같은 상품의 재진단 실행은 같은 폴더에 run-2.json, run-3.json.
    - info: 실행 정보. 열린 단계 밖에서 남긴 값도 여기
    - steps: 단계. 단계 안에 단계가 들어갈 수 있고, 모델 호출은 그 단계의 calls에 원문째
    - finish: 결말
    - prompts: 시스템 프롬프트 원문 (지문 → 원문). 호출에는 지문만
이미지는 링크만 남김. 링크가 없는 data URI(긴 이미지 조각)는 본문을 빼고 형식만.
ID는 실행 안에서 나온 순서대로 붙임(s1, c1, …). 같은 입력을 두 번 돌리면 같은 ID라 diff로 비교 가능.
판단·Tool 실행·진단서·검증 지적 ID(uuid)도 실행 안 번호(f1, e1, a1, i1, …)로 바꿔 저장 (모델 호출 본문 속 ID 포함).
실행마다 달라지는 값(시간·토큰·비용)은 호출마다 meta 한 곳에 모음 (diff 때 meta를 빼고 비교).

에러 위치
    - 예외가 처음 빠져나간 가장 안쪽 단계: error에 예외 이름·메시지·원인(__cause__)과, 실패한 호출이면 그 호출 ID
    - 그 바깥 단계: 같은 예외(또는 from으로 그 예외를 감싼 예외)면 error에 이름과 처음 실패한 단계 ID(from)만
    - 실패한 호출: error에 이름·메시지, 응답을 받았으면 본문(raw)
    - 실행이 실패로 끝나면 finish.at에 처음 실패한 단계·경로·호출
"""

import dataclasses
import hashlib
import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def to_jsonable(value: Any) -> Any:
    """JSON으로 쓸 수 있는 값으로 바꾼다. 모델·dataclass·Enum·집합도 받음.

    Args:
        value: 바꿀 값.

    Returns:
        Any: dict·list·str·int·float·bool·None으로만 된 값. 모르는 값은 repr 문자열.
    """
    # str·int를 상속한 Enum도 값으로 (먼저 검사)
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
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

    열린 단계 스택·진행 중 호출을 객체 하나에 둠 → 기록 중엔 Tool을 순차 실행 (diagnosis/job.py).
    병렬이면 단계가 서로 안에 들어가고 호출이 섞임. 스레드별로 나눠도 단계·호출 번호가 실행마다 달라져 diff 비교가 깨짐.

    Attributes:
        directory: 실행 폴더. 같은 상품의 재진단 실행은 같은 폴더에 run-2.json, run-3.json으로 쌓음.
        run_name: 이 실행의 파일 이름(확장자 뺌).
        info: 실행 정보(입력 출처·모델 설정 등). run-N.json 맨 앞에 들어감.
        steps: 맨 바깥 단계. 실행 순서대로.
        finish: 결말. 실행이 끝날 때 채움.
        prompts: 시스템 프롬프트 지문 → 원문.
    """

    def __init__(self, directory: Path, run_name: str = "run-1") -> None:
        self.directory = directory
        self.run_name = run_name
        self.info: dict[str, Any] = {}
        self.steps: list[dict[str, Any]] = []
        self.finish: dict[str, Any] | None = None
        self.prompts: dict[str, str] = {}
        self._open: list[dict[str, Any]] = []
        self._counters: dict[str, int] = {}
        self._call: dict[str, Any] | None = None
        self._failure: tuple[BaseException, dict[str, Any]] | None = None
        # 실행마다 달라지는 값(판단 ID uuid 등) → 실행 안 번호. 저장할 때 파일 전체에서 바꿈
        self._aliases: dict[str, str] = {}

    def alias(self, value: str, prefix: str) -> str:
        """실행마다 달라지는 값에 실행 안 번호를 붙인다. 같은 값은 같은 번호.

        저장할 때 파일 안 모든 문자열에서 이 값을 번호로 바꿈 (모델 호출 본문 속 값 포함).

        Args:
            value: 바꿀 값 (판단 ID 등).
            prefix: 번호 접두어 (판단 f 등).

        Returns:
            str: 접두어 + 번호 (f1, f2, …).
        """
        if value not in self._aliases:
            self._aliases[value] = self.next_id(prefix)
        return self._aliases[value]

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
            node["error"] = self._step_error(exc, node)
            raise
        finally:
            self._open.pop()

    def _step_error(self, exc: BaseException, node: dict[str, Any]) -> dict[str, Any]:
        """빠져나간 단계의 error. 안쪽 단계가 이미 남긴 예외면 이름과 그 단계 ID만.

        Args:
            exc: 단계를 빠져나간 예외.
            node: 단계 기록.

        Returns:
            dict[str, Any]: 단계에 남길 error.
        """
        if self._failure is not None and _in_chain(self._failure[0], exc):
            return {"type": type(exc).__name__, "from": self._failure[1]["step"]}
        error = error_info(exc)
        calls = node.get("calls") or []
        # 단계의 마지막 호출이 실패했으면 그 호출에서 난 예외로 봄
        if calls and "error" in calls[-1]:
            error["call"] = calls[-1]["id"]
        self._failure = (exc, {"step": node["id"], "kind": node["kind"],
                               "path": [open_node["id"] for open_node in self._open], "call": error.get("call")})
        return error

    def failure_at(self, exc: BaseException) -> dict[str, Any] | None:
        """이 예외가 처음 빠져나간 단계 위치. 단계 밖에서 난 예외면 열린 단계 밖의 마지막 실패 호출만.

        Args:
            exc: 실행을 끝낸 예외.

        Returns:
            dict[str, Any] | None: 단계 ID·종류·경로·호출 ID. 모르면 None.
        """
        if self._failure is not None and _in_chain(self._failure[0], exc):
            return self._failure[1]
        calls = self.info.get("calls") or []
        if calls and "error" in calls[-1]:
            return {"step": None, "kind": None, "path": [], "call": calls[-1]["id"]}
        return None

    def end(self, reason: str, exc: BaseException | None = None, **fields: Any) -> None:
        """결말을 남긴다. 실패면 예외 정보와 처음 실패한 위치(at)를 같이.

        Args:
            reason: 결말 (completed, failed, error 등).
            exc: 실패 원인 예외. 실패가 아니면 None.
            **fields: 결말에 같이 남길 값 (실패 코드·최종 결과 등).
        """
        finish: dict[str, Any] = {"reason": reason, **to_jsonable(fields)}
        if exc is not None:
            finish["error"] = error_info(exc)
            finish["at"] = self.failure_at(exc)
        self.finish = finish

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

    def begin_call(self, component: str, request: Any) -> None:
        """모델 호출 1건을 시작한다. 시스템 프롬프트는 prompts에 한 번만, data URI 이미지는 형식만 남김.

        Args:
            component: 에이전트 이름.
            request: 보낸 메시지 목록(채팅 모델) 또는 요청 객체(판단 모델).
        """
        call_id = self.next_id("c")
        if isinstance(request, list):
            request = [self._message(message) for message in request]
        self._call = {"id": call_id, "component": component, "request": to_jsonable(request)}

    def set_call_response(self, output: Any = None, raw: Any = None) -> None:
        """시작한 호출의 응답을 남긴다.

        Args:
            output: 스키마로 검증한 출력. 해석에 실패했으면 None.
            raw: 해석에 실패한 응답 본문. 성공이면 None.
        """
        if self._call is not None:
            self._call["output"] = to_jsonable(output)
            if raw is not None:
                self._call["raw"] = to_jsonable(raw)

    def set_call_error(self, exc: BaseException) -> None:
        """시작한 호출의 실패 원인을 남긴다.

        Args:
            exc: 실패 원인 예외.
        """
        if self._call is not None:
            self._call["error"] = error_info(exc)

    def end_call(self, meta: Any) -> str:
        """호출 1건을 실행 정보와 함께 지금 열린 단계의 calls에 넣는다. 열린 단계가 없으면 info의 calls에.

        시작하지 않은 호출이면 실행 정보만 남김.

        Args:
            meta: 호출 1건의 실행 정보 (AgentRunMeta).

        Returns:
            str: 호출 ID.
        """
        call = self._call or {"id": self.next_id("c"), "component": getattr(meta, "component", None)}
        self._call = None
        call["meta"] = to_jsonable(meta)
        (self._open[-1] if self._open else self.info).setdefault("calls", []).append(call)
        return call["id"]

    def _message(self, message: Any) -> dict[str, Any]:
        role, content = getattr(message, "type", None), getattr(message, "content", message)
        # 시스템 프롬프트는 길고 호출마다 같음 → 원문은 prompts에 한 번만, 호출엔 지문만
        if role == "system" and isinstance(content, str):
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
            self.prompts.setdefault(digest, content)
            return {"role": role, "prompt": digest}
        if isinstance(content, list):
            content = [_image_link(block) for block in content]
        return {"role": role, "content": to_jsonable(content)}

    def to_dict(self) -> dict[str, Any]:
        """run-N.json에 쓸 내용.

        Returns:
            dict[str, Any]: 실행 정보·단계·결말. 번호를 붙인 값은 번호로 바꿈.
        """
        data = {"run": self.run_name, "info": self.info, "steps": self.steps, "finish": self.finish,
                "prompts": self.prompts}
        if not self._aliases:
            return data
        # 긴 값부터 (한 값이 다른 값을 품는 경우 대비)
        pattern = re.compile("|".join(re.escape(value) for value in sorted(self._aliases, key=len, reverse=True)))
        return _replace_aliases(data, pattern, self._aliases)

    def save(self) -> Path | None:
        """run-N.json을 쓴다. 이미 있으면 덮어씀. 못 쓰면 경고 로그만 남김 (기록이 진단 결과를 바꾸지 않게).

        Returns:
            Path | None: 쓴 파일 경로. 못 썼으면 None.
        """
        path = self.directory / f"{self.run_name}.json"
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            path.write_text(_dump(self.to_dict()), encoding="utf-8")
        except OSError:
            logger.warning("trace 파일을 쓰지 못함 (path=%s)", path, exc_info=True)
            return None
        return path


def _replace_aliases(value: Any, pattern: re.Pattern[str], aliases: dict[str, str]) -> Any:
    """JSON 값 안의 모든 문자열(키 포함)에서 번호를 붙인 값을 번호로 바꾼다.

    Args:
        value: to_jsonable을 거친 값.
        pattern: 바꿀 값들을 찾는 정규식.
        aliases: 값 → 번호.

    Returns:
        Any: 바꾼 값.
    """
    if isinstance(value, str):
        return pattern.sub(lambda match: aliases[match.group(0)], value)
    if isinstance(value, dict):
        return {_replace_aliases(key, pattern, aliases): _replace_aliases(item, pattern, aliases)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_aliases(item, pattern, aliases) for item in value]
    return value


def image_link(url: str) -> str:
    """trace에 남길 이미지 주소. 링크는 그대로, data URI는 본문 대신 형식만.

    Args:
        url: http(s) 주소 또는 data URI.

    Returns:
        str: 남길 주소.
    """
    return url.split(",", 1)[0] + ",…(생략)" if url.startswith("data:") else url


def _image_link(block: Any) -> Any:
    """이미지 블록은 링크만. data URI는 본문 대신 형식만 남김 (긴 이미지 조각)."""
    url = block.get("image_url", {}).get("url") if isinstance(block, dict) else None
    if isinstance(url, str) and url.startswith("data:"):
        return {"type": "image_url", "image_url": {"url": image_link(url)}}
    return block


# 예외 메시지 상한 (응답 본문이 통째로 들어가는 메시지 대비)
_MESSAGE_LIMIT = 1000
# 원인 예외를 따라갈 깊이
_CAUSE_DEPTH = 3


def error_info(exc: BaseException, depth: int = _CAUSE_DEPTH) -> dict[str, Any]:
    """trace에 남길 예외 정보. 원인 예외(__cause__)는 몇 단계까지 같이.

    Args:
        exc: 예외.
        depth: 따라갈 원인 예외 깊이.

    Returns:
        dict[str, Any]: 이름·메시지(길면 자름)·원인.
    """
    info: dict[str, Any] = {"type": type(exc).__name__, "message": str(exc)[:_MESSAGE_LIMIT]}
    if exc.__cause__ is not None and depth > 0:
        info["cause"] = error_info(exc.__cause__, depth - 1)
    return info


def _in_chain(inner: BaseException, exc: BaseException) -> bool:
    """exc가 inner 자신이거나 inner를 원인으로 감싼 예외인지.

    원인(__cause__, ``raise ... from``)만 따라감. 처리 중 난 예외(__context__)는 다른 실패로 봄.

    Args:
        inner: 안쪽에서 먼저 본 예외.
        exc: 지금 빠져나가는 예외.

    Returns:
        bool: 같은 실패면 True.
    """
    current: BaseException | None = exc
    while current is not None:
        if current is inner:
            return True
        current = current.__cause__
    return False


_trace: ContextVar[TraceRecorder | None] = ContextVar("trace", default=None)


@contextmanager
def trace_run(directory: Path, run_name: str = "run-1") -> Iterator[TraceRecorder]:
    """이 블록의 실행을 새 trace에 기록하고, 끝나면 run-N.json을 쓴다.

    실패로 빠져나가도 거기까지 기록을 씀. 결말을 안 채웠으면 실패 예외와 처음 실패한 위치를 결말로 남김.

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
            recorder.end("error", exc)
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


def trace_append(key: str, value: Any) -> None:
    """기록 중이면 지금 열린 단계의 목록에 값을 하나 더한다. 기록 중이 아니면 아무것도 안 함.

    한 단계에서 여러 번 일어나는 일(후보 고르기 등)을 차례로 남길 때 씀.

    Args:
        key: 목록 이름.
        value: 더할 값.
    """
    recorder = _trace.get()
    if recorder is not None:
        target = recorder.current_step() or recorder.info
        target.setdefault(key, []).append(to_jsonable(value))


def trace_note(key: str, value: Any) -> None:
    """기록 중이면 지금 열린 단계에 값을 남긴다. 기록 중이 아니면 아무것도 안 함.

    Args:
        key: 값 이름.
        value: 남길 값.
    """
    recorder = _trace.get()
    if recorder is not None:
        recorder.note(key, value)


def trace_finish(reason: str, exc: BaseException | None = None, **fields: Any) -> None:
    """기록 중이면 결말을 남긴다. 기록 중이 아니면 아무것도 안 함.

    예외를 잡아 결과로 바꾸는 곳(진단 함수의 단계 실패 등)에서 씀. 잡지 않은 예외는 trace_run이 남김.

    Args:
        reason: 결말 (completed, failed 등).
        exc: 실패 원인 예외. 실패가 아니면 None.
        **fields: 결말에 같이 남길 값.
    """
    recorder = _trace.get()
    if recorder is not None:
        recorder.end(reason, exc, **fields)


def trace_alias(value: str, prefix: str) -> str:
    """기록 중이면 실행마다 달라지는 값의 실행 안 번호. 기록 중이 아니면 값 그대로.

    Args:
        value: 바꿀 값 (판단 ID 등).
        prefix: 번호 접두어 (판단 f 등).

    Returns:
        str: 번호 (f1, f2, …) 또는 값 그대로.
    """
    recorder = _trace.get()
    return value if recorder is None else recorder.alias(value, prefix)
