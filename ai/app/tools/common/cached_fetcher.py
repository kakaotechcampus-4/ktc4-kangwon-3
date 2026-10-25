"""외부 API 응답을 DB에서 먼저 찾고, 없으면 클라이언트로 받아 저장하는 조회 객체.

클라이언트가 해석까지 끝낸 응답 스키마를 그대로 JSON으로 저장하고, 꺼낼 때 같은 스키마로 되돌린다.
그래서 Tool은 클라이언트 자리에 이 객체를 넣기만 하면 되고 데이터 로직은 바뀌지 않는다.
"""

import hashlib
import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...config import CACHE_DB_RETRY_SECONDS
from ...models import ApiResponseCache
from ...repositories.api_response_cache import ApiResponseCacheRepository

logger = logging.getLogger(__name__)

_R = TypeVar("_R", bound=BaseModel)


def request_key(request: BaseModel) -> str:
    """요청 스키마의 캐시 키. 필드 순서와 무관하게 같은 요청이면 같은 값이다.

    Args:
        request: 클라이언트 요청 스키마. 키·OC 같은 비밀값은 클라이언트 생성자에 있어 들어가지 않는다.

    Returns:
        str: 정렬한 요청 JSON의 sha256 16진수(64자).
    """
    text = json.dumps(request.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CachedFetcher(Generic[_R]):
    """클라이언트와 응답 캐시 저장소를 묶은 조회 객체. 클라이언트처럼 fetch_parsed·close를 가진다.

    - DB에 있고 만료 전이면 DB 값을 돌려준다.
    - 없거나 만료됐으면 클라이언트로 받아 DB에 저장하고 돌려준다.
    - 클라이언트 호출이 실패하면 use_stale_on_error일 때만 만료된 DB 값을 돌려준다.
    - DB가 없거나 실패하면 캐시 없이 클라이언트만 쓴다(실패 뒤 일정 시간은 DB를 건너뜀).
    - 저장된 값이 지금 스키마로 읽히지 않으면 없는 것으로 보고 다시 받는다.

    Args:
        client: fetch_parsed·close를 가진 클라이언트.
        name: 캐시 구분 이름(예: "law.text"). 같은 요청 스키마를 쓰는 클라이언트끼리 겹치지 않게 한다.
        response_type: 클라이언트 응답 스키마. DB 값을 되돌릴 때 쓴다.
        ttl: 보관 시간. None이면 영구 보관(버전이 고정된 본문).
        session_factory: DB 세션을 만드는 함수. None이면 캐시 없이 클라이언트만 쓴다.
        use_stale_on_error: 클라이언트 호출 실패 시 만료된 DB 값을 쓸지.
        clock: 현재 시각(UTC). 테스트용.
        monotonic: DB 건너뛰기 시간 계산용 시계. 테스트용.
    """

    def __init__(self, client, *, name: str, response_type: type[_R], ttl: timedelta | None,
                 session_factory: Callable[[], Session] | None, use_stale_on_error: bool = False,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 monotonic: Callable[[], float] = time.monotonic):
        self._client = client
        self._name = name
        self._response_type = response_type
        self._ttl = ttl
        self._session_factory = session_factory
        self._use_stale = use_stale_on_error
        self._clock = clock
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._db_skip_until = 0.0

    def fetch_parsed(self, request: BaseModel) -> _R:
        """요청 하나의 응답 스키마를 돌려준다. 클라이언트를 직접 부른 결과와 같다.

        Args:
            request: 클라이언트 요청 스키마.

        Returns:
            _R: 응답 스키마.

        Raises:
            Exception: 클라이언트 호출 실패. 만료된 DB 값도 쓸 수 없으면 그대로 올린다.
        """
        key = request_key(request)
        cached = self._read(key)
        now = self._clock()
        if cached is not None and (cached[1] is None or cached[1] > now):
            return cached[0]
        try:
            response = self._client.fetch_parsed(request)
        except Exception:
            if self._use_stale and cached is not None:
                logger.warning("%s 조회 실패 — 만료된 캐시로 대신함 (만료 %s)", self._name, cached[1])
                return cached[0]
            raise
        self._write(key, request, response, now)
        return response

    def close(self) -> None:
        """클라이언트 연결을 정리한다."""
        self._client.close()

    # -- DB --

    def _db_available(self) -> bool:
        with self._lock:
            return self._session_factory is not None and self._monotonic() >= self._db_skip_until

    def _db_failed(self, action: str, error: Exception) -> None:
        with self._lock:
            self._db_skip_until = self._monotonic() + CACHE_DB_RETRY_SECONDS
        logger.warning("%s 캐시 %s 실패 — %d초 동안 DB 건너뜀: %s",
                       self._name, action, CACHE_DB_RETRY_SECONDS, type(error).__name__)

    def _read(self, key: str) -> tuple[_R, datetime | None] | None:
        """DB 값과 만료 시각. 없거나·읽을 수 없거나·DB를 못 쓰면 None."""
        if not self._db_available():
            return None
        try:
            with self._session_factory() as session:
                row = ApiResponseCacheRepository(session).get(self._name, key)
                if row is None:
                    return None
                payload, expires_at = row.response, row.expires_at
        except SQLAlchemyError as e:
            self._db_failed("조회", e)
            return None
        try:
            return self._response_type.model_validate(payload), expires_at
        except ValidationError:
            # 응답 스키마가 바뀐 뒤의 옛 값 → 다시 받아 덮어씀
            logger.warning("%s 캐시 값이 지금 응답 스키마와 맞지 않아 다시 조회함", self._name)
            return None

    def _write(self, key: str, request: BaseModel, response: _R, now: datetime) -> None:
        if not self._db_available():
            return
        entry = ApiResponseCache(
            client=self._name, request_key=key, request=request.model_dump(mode="json"),
            response=response.model_dump(mode="json"),
            expires_at=None if self._ttl is None else now + self._ttl,
        )
        try:
            with self._session_factory() as session:
                ApiResponseCacheRepository(session).put(entry)
                session.commit()
        except SQLAlchemyError as e:
            self._db_failed("저장", e)
