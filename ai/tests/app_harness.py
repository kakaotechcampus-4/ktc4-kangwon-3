"""앱을 가짜 기동 부품으로 띄우는 테스트 도구. test_main·test_flow·startup 테스트가 같이 씀.

- app_env: 실제 ai/.env·DB·Sentry 없이 기동할 설정 (테스트 모듈의 autouse fixture에서 yield from)
- FakeBackend: 콜백을 받는 가짜 BE (httpx.MockTransport)
- fake_parts·client: 가짜 부품 묶음과 그 부품으로 띄울 앱의 클라이언트
"""

import json
import logging
import threading
import time
from collections.abc import Callable, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.clients.backend import BackendCallbackClient
from app.db import engine as database
from app.dummy import job as dummy_job, run_case_diagnosis
from app.observability.logs import APP_LOGGER
from app.routers import _dummy
from app.sessions.manager import SessionManager
from app.startup.parts import AppParts

TOKEN = "test-internal-token-0123456789abcdef"
BE_BASE_URL = "http://be-server:8080"
_ENV = {
    "OPENAI_API_KEY": "test-key",
    "OPENAI_BASE_URL": "https://mlapi.run/example/v1",
    "OPENAI_EMBEDDING_MODEL": "openai/text-embedding-3-small",
    "DATA_GO_KR_KEY": "test-data-key",
    "KEY_SAFETYKOREA": "test-safety-key",
    "LAW_GO_KR_OC": "test-oc",
    "INTERNAL_API_TOKEN": TOKEN,
    "BE_BASE_URL": BE_BASE_URL,
    "REVIEW_TEXT_HIGH": "0.85",
    "REVIEW_TEXT_LOW": "0.3",
    "REVIEW_IMAGE_HIGH": "0.8",
    "REVIEW_IMAGE_LOW": "0.3",
}
# 셸·ai/.env에 있어도 테스트에선 지움 (DB 없이 기동, 오류를 실제 Sentry로 안 보냄)
_UNSET = ("DATABASE_URL", "MODEL_PROFILE_OVERRIDES", "AI_DEV_API_ENABLED", "AI_DEV_API_KEY",
          "SENTRY_DSN", "SENTRY_ENVIRONMENT")
_CACHES = (config.get_settings, database.get_engine, database.get_session_factory)


def app_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """테스트 설정을 깔고, 끝나면 설정 캐시와 lifespan이 바꾼 app 로그 핸들러·레벨을 되돌린다.

    Args:
        monkeypatch: 환경변수·속성 교체용.

    Yields:
        None: 테스트 실행 구간.
    """
    monkeypatch.setattr(config.settings, "load_dotenv", lambda **kwargs: False)
    for name, value in _ENV.items():
        monkeypatch.setenv(name, value)
    for name in _UNSET:
        monkeypatch.delenv(name, raising=False)
    # 더미 진단 단계 대기 없이
    monkeypatch.setattr(_dummy, "DUMMY_STAGE_SECONDS", 0)
    monkeypatch.setattr(dummy_job, "STAGE_SECONDS", 0)
    for cached in _CACHES:
        cached.cache_clear()
    logger = logging.getLogger(APP_LOGGER)
    handlers, level = list(logger.handlers), logger.level
    yield
    logger.handlers[:] = handlers
    logger.setLevel(level)
    for cached in _CACHES:
        cached.cache_clear()


def wait_until(condition: Callable[[], object], timeout: float = 5.0) -> None:
    """조건이 참이 될 때까지 기다린다.

    Raises:
        AssertionError: timeout 안에 참이 되지 않은 경우.
    """
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("조건을 기다리다 시간 초과")
        time.sleep(0.01)


class FakeBackend:
    """콜백을 받는 가짜 BE. respond로 이벤트마다 응답 상태를 정함 (기본 200)."""

    def __init__(self, respond: Callable[[dict], int] = lambda event: 200):
        self.requests: list[httpx.Request] = []
        self.statuses: list[int] = []
        self._respond = respond
        self._lock = threading.Lock()

    def handle(self, request: httpx.Request) -> httpx.Response:
        event = json.loads(request.content)
        with self._lock:
            status = self._respond(event)
            self.requests.append(request)
            self.statuses.append(status)
        code = "OK" if status == 200 else "COMMON-001"
        return httpx.Response(status, json={"code": code, "message": "", "data": None})

    @property
    def events(self) -> list[dict]:
        """받은 이벤트 전부 (재전송 포함, 받은 순서)."""
        with self._lock:
            return [json.loads(request.content) for request in self.requests]

    def accepted(self) -> list[dict]:
        """200으로 받은 이벤트 (받은 순서)."""
        with self._lock:
            return [json.loads(request.content) for request, status in zip(self.requests, self.statuses)
                    if status == 200]

    def wait_for(self, event_type: str, timeout: float = 5.0) -> dict:
        """그 종류 이벤트를 200으로 받을 때까지 기다려 마지막 것을 돌려준다.

        Raises:
            AssertionError: timeout 안에 받지 못한 경우.
        """
        deadline = time.monotonic() + timeout
        while not (found := [event for event in self.accepted() if event["eventType"] == event_type]):
            if time.monotonic() > deadline:
                raise AssertionError(f"{event_type} 콜백을 기다리다 시간 초과: {self.events}")
            time.sleep(0.01)
        return found[-1]


def fake_parts(backend: FakeBackend, **overrides) -> AppParts:
    """가짜 기동 부품. 진단은 고정 더미(모델·외부 호출 없음), 콜백은 backend로, DB 없음.

    Args:
        backend: 콜백을 받을 가짜 BE.
        **overrides: 바꿀 부품 (AppParts 필드 이름).

    Returns:
        AppParts: 가짜 부품 묶음.
    """
    parts = {
        "pipeline_job": _dummy.run_dummy_diagnosis,
        "dummy_job": run_case_diagnosis,
        "callback_sender": BackendCallbackClient(BE_BASE_URL, TOKEN, transport=httpx.MockTransport(backend.handle)),
        "database": None,
        "session_manager": SessionManager,
        "sweep_seconds": config.SESSION_SWEEP_SECONDS,
        "drain_seconds": config.SESSION_DRAIN_SECONDS,
    }
    return AppParts(**(parts | overrides))


def client(parts: AppParts, **kwargs) -> TestClient:
    """가짜 부품으로 띄울 앱의 클라이언트. with로 열면 기동, 닫으면 종료.

    Args:
        parts: 기동 부품.
        **kwargs: TestClient 옵션 (headers 등).

    Returns:
        TestClient: 앱 클라이언트.
    """
    return TestClient(main.create_app(lambda settings: parts), **kwargs)
