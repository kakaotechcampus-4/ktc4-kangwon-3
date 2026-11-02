"""앱 로그 설정 (#497).

서버는 uvicorn만 실행해 로그 설정이 없으면 파이썬 기본값(WARNING 이상)만 나옴.
``app`` 로거에만 핸들러·레벨을 붙임. uvicorn 로거는 uvicorn 설정 그대로,
외부 라이브러리(httpx 등)는 WARNING 이상만 (요청 주소에 API 키가 들어가는 로그 방지).

진단 실행 중 남긴 줄에는 실행 정보(진단서·상품·실행 ID, 실행 종류)를 줄 끝에 ``key=value``로 붙임.
실행 정보는 문맥 변수라 남기는 쪽 코드는 고치지 않음. 새 스레드로는 자동으로 안 넘어감
→ 스레드를 띄우는 쪽에서 ``contextvars.copy_context().run``으로 넘김.
"""

import logging
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from types import MappingProxyType

from ..domain.context import ExecutionContext

APP_LOGGER = "app"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s%(run_fields)s"
# 형식을 맞출 uvicorn 로거. uvicorn.error는 uvicorn으로 넘겨 따로 핸들러가 없음
UVICORN_LOGGERS = ("uvicorn", "uvicorn.access")

# 지금 실행의 로그 필드. 실행 밖이면 비어 있음
_run_fields: ContextVar[Mapping[str, str]] = ContextVar("run_log_fields", default=MappingProxyType({}))


@contextmanager
def run_log_context(context: ExecutionContext) -> Iterator[None]:
    """이 블록에서 남긴 로그 줄에 실행 정보를 붙인다. 나가면 이전 값으로 되돌림.

    Args:
        context: 이 실행의 컨텍스트. 값이 없는 필드(단독 실행의 진단서 ID)는 뺌.
    """
    with log_fields({
        "diagnosis_id": context.diagnosis_id,
        "product_id": context.product_id,
        "run_id": context.run_id,
        "run_type": context.run_type.value,
    }):
        yield


@contextmanager
def log_fields(fields: Mapping[str, str | None]) -> Iterator[None]:
    """이 블록에서 남긴 로그 줄에 주어진 필드를 붙인다. 실행 컨텍스트가 없는 곳(콜백 발신함 등)용.

    Args:
        fields: 필드 이름 → 값. None인 필드는 뺌.
    """
    token = _run_fields.set(MappingProxyType({key: value for key, value in fields.items() if value is not None}))
    try:
        yield
    finally:
        _run_fields.reset(token)


def set_run_field(name: str, value: object) -> None:
    """지금 실행의 로그 필드 하나를 넣거나 바꾼다. 실행 밖이면 무시.

    단계·재실행 회차처럼 실행 중 바뀌는 값용. ``run_log_context``를 나가면 함께 사라짐.

    Args:
        name: 필드 이름 (``stage``, ``retry_round`` 등).
        value: 값. 문자열로 붙임.
    """
    fields = _run_fields.get()
    if fields:
        _run_fields.set(MappingProxyType({**fields, name: str(value)}))


def current_run_fields() -> Mapping[str, str]:
    """지금 실행의 로그 필드. 실행 밖이면 빈 매핑.

    Returns:
        Mapping[str, str]: 필드 이름 → 값.
    """
    return _run_fields.get()


class _RunFieldsFilter(logging.Filter):
    """줄 끝에 붙일 실행 정보를 ``run_fields``로 넣음. 실행 밖이면 빈 문자열."""

    def filter(self, record: logging.LogRecord) -> bool:
        fields = _run_fields.get()
        record.run_fields = "".join(f" {key}={value}" for key, value in fields.items())
        return True


# 핸들러마다 같은 필터 하나. 다시 설정해도 필터가 쌓이지 않음 (addFilter는 같은 객체를 두 번 넣지 않음)
_RUN_FIELDS_FILTER = _RunFieldsFilter()


class _AppHandler(logging.StreamHandler):
    """이 모듈이 붙인 핸들러 표시. 다시 설정해도 줄이 두 번 찍히지 않게 찾아서 바꿈."""


def configure_logging(level: str) -> None:
    """``app`` 로거를 표준 에러로 내보내게 설정한다. 여러 번 불러도 핸들러는 하나.

    uvicorn이 붙인 핸들러(기동·접근 로그)도 같은 형식으로 맞춤. 시각이 없는 uvicorn 기본 형식이면
    앱 줄과 시간순으로 맞춰 보기 어려움. 레벨·출력 위치는 uvicorn 설정 그대로.

    Args:
        level: 로그 레벨 이름 (DEBUG·INFO·WARNING·ERROR).
    """
    logger = logging.getLogger(APP_LOGGER)
    for handler in [h for h in logger.handlers if isinstance(h, _AppHandler)]:
        logger.removeHandler(handler)
    handler = _AppHandler(sys.stderr)
    _use_app_format(handler)
    logger.addHandler(handler)
    # 루트로 넘기는 것은 그대로 (pytest caplog가 루트에서 받음). 서버는 루트에 핸들러가 없어 두 번 안 찍힘
    logger.setLevel(level)
    # uvicorn은 앱 lifespan 전에 자기 로거를 설정함 → 여기서 형식만 바꿈. uvicorn 없이 띄우면 핸들러가 없어 그대로
    for name in UVICORN_LOGGERS:
        for uvicorn_handler in logging.getLogger(name).handlers:
            _use_app_format(uvicorn_handler)


def _use_app_format(handler: logging.Handler) -> None:
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(_RUN_FIELDS_FILTER)
