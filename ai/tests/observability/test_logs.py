"""앱 로그 설정 테스트."""

import io
import logging
import re

import pytest

from app.domain.context import ExecutionContext, RunType
from app.observability.logs import (
    APP_LOGGER,
    configure_logging,
    current_run_fields,
    log_fields,
    run_log_context,
    set_run_field,
)


@pytest.fixture(autouse=True)
def _restore_app_logger():
    """테스트가 바꾼 app 로거 핸들러·레벨과 uvicorn 접근 로그 필터를 되돌림."""
    logger = logging.getLogger(APP_LOGGER)
    access = logging.getLogger("uvicorn.access")
    handlers, level, access_filters = list(logger.handlers), logger.level, list(access.filters)
    yield
    logger.handlers[:] = handlers
    logger.setLevel(level)
    access.filters[:] = access_filters


def _own_handlers():
    return [h for h in logging.getLogger(APP_LOGGER).handlers if type(h).__name__ == "_AppHandler"]


def test_여러_번_설정해도_핸들러는_하나고_마지막_레벨을_쓴다():
    configure_logging("INFO")
    configure_logging("DEBUG")

    assert len(_own_handlers()) == 1
    assert logging.getLogger(APP_LOGGER).level == logging.DEBUG


def test_app_아래_로거의_INFO가_시각·레벨·이름과_함께_나간다(capsys):
    configure_logging("INFO")

    logging.getLogger("app.sessions.manager").info("진단 접수")

    line = capsys.readouterr().err.strip()
    assert line.endswith("INFO app.sessions.manager: 진단 접수")


def test_실행_안에서_남긴_줄에는_실행_정보가_붙고_밖에서는_안_붙는다(capsys):
    configure_logging("INFO")
    logger = logging.getLogger("app.tools.electrical")
    context = ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION, diagnosis_id="d-1")

    with run_log_context(context):
        logger.info("안쪽")
    logger.info("바깥")

    inside, outside = capsys.readouterr().err.strip().splitlines()
    assert inside.endswith(f"안쪽 diagnosis_id=d-1 product_id=p-1 run_id={context.run_id} run_type=production")
    assert outside.endswith("app.tools.electrical: 바깥")


def test_진단서_ID가_없는_실행은_그_필드를_뺀다():
    context = ExecutionContext.start(product_id="dev-1", run_type=RunType.TEST)

    with run_log_context(context):
        fields = dict(current_run_fields())

    assert fields == {"product_id": "dev-1", "run_id": context.run_id, "run_type": "test"}


def test_실행_중_바꾼_필드는_실행이_끝나면_사라지고_실행_밖에서는_무시한다():
    context = ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION)

    set_run_field("stage", "selection")
    with run_log_context(context):
        set_run_field("stage", "selection")
        set_run_field("retry_round", 1)
        inside = dict(current_run_fields())

    assert (inside["stage"], inside["retry_round"]) == ("selection", "1")
    assert dict(current_run_fields()) == {}


def test_실행_컨텍스트가_없는_곳은_필드를_직접_붙이고_None은_뺀다():
    with log_fields({"product_id": "p-1", "diagnosis_id": None}):
        inside = dict(current_run_fields())

    assert inside == {"product_id": "p-1"}
    assert dict(current_run_fields()) == {}


def test_외부_라이브러리_로거는_건드리지_않는다(capsys):
    # httpx는 INFO로 요청 주소를 남기고, 공공 API 주소에는 서비스 키가 들어감
    configure_logging("DEBUG")

    logging.getLogger("httpx").info("HTTP Request: GET https://apis.data.go.kr/?serviceKey=secret")

    assert "serviceKey" not in capsys.readouterr().err


def test_uvicorn이_붙인_핸들러도_시각이_있는_앱_형식으로_맞춘다():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    access = logging.getLogger("uvicorn.access")
    access.addHandler(handler)
    try:
        configure_logging("INFO")
        configure_logging("INFO")
        access.warning('%s - "%s %s HTTP/%s" %d', "127.0.0.1:1234", "POST", "/api/ai/v1/diagnose/resume", "1.1", 422)
    finally:
        access.removeHandler(handler)

    line = stream.getvalue().strip()
    assert re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} WARNING uvicorn.access: '
                        r'127.0.0.1:1234 - "POST /api/ai/v1/diagnose/resume HTTP/1.1" 422', line)
    assert len(handler.filters) == 1


@pytest.mark.parametrize(("method", "path", "status", "kept"), [
    ("GET", "/api/ai/v1/health", 200, False),
    ("GET", "/metrics", 200, False),
    ("GET", "/metrics?name[]=ai_sessions", 200, False),
    ("GET", "/api/ai/v1/health", 503, True),
    ("GET", "/api/ai/v1/health/ready", 200, True),
    ("POST", "/api/ai/v1/diagnose/content", 202, True),
])
def test_헬스체크·지표_수집의_성공_응답만_접근_로그에서_뺀다(method, path, status, kept):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    access = logging.getLogger("uvicorn.access")
    access.addHandler(handler)
    try:
        configure_logging("INFO")
        access.warning('%s - "%s %s HTTP/%s" %d', "127.0.0.1:1234", method, path, "1.1", status)
    finally:
        access.removeHandler(handler)

    assert bool(stream.getvalue()) is kept
