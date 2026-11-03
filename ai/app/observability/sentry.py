"""Sentry 오류 전송 설정.

진단은 세션 스레드에서 돌고 실패를 잡아 로그로 남김 → 요청 예외만으로는 대부분 안 잡힘.
그래서 로그 기준(AI_LOGGING.md 3절)을 그대로 씀.
    - ERROR 로그(예상 못 한 예외, traceback 포함) → 이벤트
    - INFO·WARNING 로그 → 이벤트 앞의 흐름 기록(breadcrumb)만
    - 요청 처리 중 잡지 않은 예외(500) → 이벤트 (FastAPI 연동). 예외 처리기가 응답으로 바꾼 4xx는 안 감
요청 본문·개인정보·지역 변수(상품 원문·요청 헤더가 담김)는 보내지 않음. 트레이스·로그 전송은 쓰지 않음.
보내기 직전 내부 인증 헤더를 빼고, 예외 메시지·로그 문구·추가 값·흐름 기록 속 URL의 키(serviceKey·OC)를 가림.
진단 실행 중 이벤트엔 로그와 같은 실행 정보(진단서·상품·실행 ID, 실행 종류, 단계, 재실행 회차)를 태그로 붙임.
"""

import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from ..clients.base import mask_sensitive_params
from ..routers.dev_auth import DEV_API_KEY_HEADER
from ..routers.internal_auth import INTERNAL_TOKEN_HEADER
from .logs import current_run_fields

logger = logging.getLogger(__name__)

# 요청 헤더에서 뺄 이름 (소문자). Authorization·Cookie는 SDK가 이미 가림
_SECRET_HEADERS = frozenset({INTERNAL_TOKEN_HEADER.lower(), DEV_API_KEY_HEADER.lower()})


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
        # 오류 위치별 지역 변수를 보내지 않음. 요청 헤더(내부 토큰)·상품 원문·키가 든 URL이 그대로 실림
        include_local_variables=False,
        integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
        before_send=before_send,
        **options,
    )
    logger.info("Sentry 켜짐 (environment=%s)", environment)
    return True


def before_send(event: dict, hint: dict) -> dict:
    """보내기 직전 이벤트의 민감 정보를 지우고 지금 실행 정보를 태그로 붙인다.

    이벤트를 남긴 스레드에서 불림 → 로그 줄과 같은 실행 정보. 실행 밖(기동·요청 처리 등)이면 태그 없음.

    Args:
        event: Sentry 이벤트.
        hint: 원래 예외 등 (안 씀).

    Returns:
        dict: 정리하고 태그를 붙인 이벤트.
    """
    _scrub(event)
    fields = current_run_fields()
    if fields:
        event.setdefault("tags", {}).update(fields)
    return event


def _scrub(event: dict) -> None:
    """내부 인증 헤더를 빼고, 예외 메시지·로그 문구·추가 값·흐름 기록 속 URL의 키를 가린다.

    Args:
        event: 고칠 Sentry 이벤트 (그 자리에서 바꿈).
    """
    headers = event.get("request", {}).get("headers")
    if isinstance(headers, dict):
        for name in [name for name in headers if name.lower() in _SECRET_HEADERS]:
            del headers[name]
    for exception in event.get("exception", {}).get("values", []):
        _mask_key(exception, "value")
    logentry = event.get("logentry", {})
    _mask_key(logentry, "message")
    _mask_key(logentry, "formatted")
    # 로그 인자 (logger.error("... %s", url)의 url)
    params = logentry.get("params")
    if isinstance(params, list):
        logentry["params"] = [_mask_text(param) if isinstance(param, str) else param for param in params]
    # 로그 extra 값
    _mask_values(event.get("extra"))
    for breadcrumb in event.get("breadcrumbs", {}).get("values", []):
        _mask_key(breadcrumb, "message")
        # 외부 호출 기록의 url·http.query (SDK가 httpx 호출마다 남김), 로그 기록의 extra 값
        _mask_values(breadcrumb.get("data"))


def _mask_values(values: dict | None) -> None:
    """dict의 문자열 값마다 URL의 키를 가린다. dict가 아니면 그대로."""
    if isinstance(values, dict):
        for key in values:
            _mask_key(values, key)


def _mask_key(item: dict, key: str) -> None:
    """item[key]가 문자열이면 URL의 키를 가린다."""
    if isinstance(item.get(key), str):
        item[key] = _mask_text(item[key])


def _mask_text(text: str) -> str:
    """URL의 키를 가린다. ?가 없는 쿼리 문자열(serviceKey=...&x=1)도 가림.

    Args:
        text: 가릴 문자열.

    Returns:
        str: 키 값이 가려진 문자열.
    """
    # 맨 앞 파라미터도 잡히게 ?를 붙여 가린 뒤 다시 뗌
    return mask_sensitive_params(f"?{text}")[1:]
