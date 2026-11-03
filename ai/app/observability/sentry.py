"""Sentry 오류 전송 설정.

진단은 세션 스레드에서 돌고 실패를 잡아 로그로 남김 → 요청 예외만으로는 대부분 안 잡힘.
그래서 로그 기준(AI_LOGGING.md 3절)을 그대로 씀.
    - ERROR 로그(예상 못 한 예외, traceback 포함) → 이벤트
    - INFO·WARNING 로그 → 이벤트 앞의 흐름 기록(breadcrumb)만
    - 요청 처리 중 잡지 않은 예외(500) → 이벤트 (FastAPI 연동). 예외 처리기가 응답으로 바꾼 4xx는 안 감
요청 본문·개인정보는 보내지 않음. 트레이스·로그 전송은 쓰지 않음.
진단 실행 중 이벤트엔 로그와 같은 실행 정보(진단서·상품·실행 ID, 실행 종류, 단계, 재실행 회차)를 태그로 붙임.
"""

import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from .logs import current_run_fields

logger = logging.getLogger(__name__)


def configure_sentry(dsn: str, environment: str, **options) -> bool:
    """Sentry를 켠다. DSN이 비면 아무것도 안 함.

    Args:
        dsn: Sentry 프로젝트 주소. 비면 끔.
        environment: 환경 이름 (운영·개발 구분).
        **options: sentry_sdk.init에 그대로 넘길 값 (테스트의 전송 바꾸기 등).

    Returns:
        bool: 켰으면 True.
    """
    if not dsn:
        logger.info("Sentry 꺼짐 (SENTRY_DSN 없음)")
        return False
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        # IP·쿠키를 보내지 않음
        send_default_pii=False,
        # 요청 본문(상품 원문)을 보내지 않음. 기본값(medium)은 개인정보 설정과 상관없이 본문을 보냄
        max_request_body_size="never",
        # 오류만. 성능 트레이스는 안 씀
        traces_sample_rate=None,
        integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
        before_send=before_send,
        **options,
    )
    logger.info("Sentry 켜짐 (environment=%s)", environment)
    return True


def before_send(event: dict, hint: dict) -> dict:
    """보내기 직전 이벤트에 지금 실행 정보를 태그로 붙인다. 실행 밖(기동·요청 처리 등)이면 그대로.

    이벤트를 남긴 스레드에서 불림 → 로그 줄과 같은 실행 정보.

    Args:
        event: Sentry 이벤트.
        hint: 원래 예외 등 (안 씀).

    Returns:
        dict: 태그를 붙인 이벤트.
    """
    fields = current_run_fields()
    if fields:
        event.setdefault("tags", {}).update(fields)
    return event
