"""앱 로그 설정 (#497).

서버는 uvicorn만 실행해 로그 설정이 없으면 파이썬 기본값(WARNING 이상)만 나옴.
``app`` 로거에만 핸들러·레벨을 붙임. uvicorn 로거는 uvicorn 설정 그대로,
외부 라이브러리(httpx 등)는 WARNING 이상만 (요청 주소에 API 키가 들어가는 로그 방지).
"""

import logging
import sys

APP_LOGGER = "app"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class _AppHandler(logging.StreamHandler):
    """이 모듈이 붙인 핸들러 표시. 다시 설정해도 줄이 두 번 찍히지 않게 찾아서 바꿈."""


def configure_logging(level: str) -> None:
    """``app`` 로거를 표준 에러로 내보내게 설정한다. 여러 번 불러도 핸들러는 하나.

    Args:
        level: 로그 레벨 이름 (DEBUG·INFO·WARNING·ERROR).
    """
    logger = logging.getLogger(APP_LOGGER)
    for handler in [h for h in logger.handlers if isinstance(h, _AppHandler)]:
        logger.removeHandler(handler)
    handler = _AppHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    # 루트로 넘기는 것은 그대로 (pytest caplog가 루트에서 받음). 서버는 루트에 핸들러가 없어 두 번 안 찍힘
    logger.setLevel(level)
