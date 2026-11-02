"""앱 로그 설정 테스트."""

import logging

import pytest

from app.observability.logs import APP_LOGGER, configure_logging


@pytest.fixture(autouse=True)
def _restore_app_logger():
    """테스트가 바꾼 app 로거 핸들러·레벨을 되돌림."""
    logger = logging.getLogger(APP_LOGGER)
    handlers, level = list(logger.handlers), logger.level
    yield
    logger.handlers[:] = handlers
    logger.setLevel(level)


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


def test_외부_라이브러리_로거는_건드리지_않는다(capsys):
    # httpx는 INFO로 요청 주소를 남기고, 공공 API 주소에는 서비스 키가 들어감
    configure_logging("DEBUG")

    logging.getLogger("httpx").info("HTTP Request: GET https://apis.data.go.kr/?serviceKey=secret")

    assert "serviceKey" not in capsys.readouterr().err
