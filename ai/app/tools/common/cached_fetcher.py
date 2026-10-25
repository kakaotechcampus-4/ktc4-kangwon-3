"""외부 API 응답을 DB에서 먼저 찾고, 없으면 클라이언트로 받아 저장하는 조회 객체.

클라이언트가 해석까지 끝낸 응답 스키마를 그대로 JSON으로 저장하고, 꺼낼 때 같은 스키마로 되돌린다.
그래서 Tool은 클라이언트 자리에 이 객체를 넣기만 하면 되고 데이터 로직은 바뀌지 않는다.

- ScheduledFetcher: 미리 쌓아 두고 스케줄러가 주기적으로 점검하는 데이터(법령·행정규칙 검색·본문).
- OnDemandFetcher: 무엇이 필요할지 미리 알 수 없어 조회할 때 쌓는 데이터(관세청 확인기관).
"""

import hashlib
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Generic, NamedTuple, TypeVar

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


class _Cached(NamedTuple, Generic[_R]):
    response: _R
    expires_at: datetime | None


class CachedFetcherBase(ABC, Generic[_R]):
    """클라이언트와 응답 캐시 저장소를 묶은 조회 객체의 공통 부분. 클라이언트처럼 fetch_parsed·close를 가진다.

    - DB에 있고 만료 전이면 DB 값을 돌려준다.
    - 없거나 만료됐으면 클라이언트로 받아 DB에 저장하고 돌려준다.
    - 클라이언트 호출이 실패하면 USE_STALE_ON_ERROR인 종류만 만료된 DB 값을 돌려준다.
    - DB가 없거나 실패하면 캐시 없이 클라이언트만 쓴다(실패 뒤 일정 시간은 DB를 건너뜀).
    - 저장된 값이 지금 스키마로 읽히지 않으면 없는 것으로 보고 다시 받는다.

    하위 클래스는 만료 시각(_expires_at)과 실패 시 만료 값 사용 여부(USE_STALE_ON_ERROR)만 정한다.

    Args:
        client: fetch_parsed·close를 가진 클라이언트.
        name: 캐시 구분 이름(예: "law.text"). 같은 요청 스키마를 쓰는 클라이언트끼리 겹치지 않게 한다.
        response_type: 클라이언트 응답 스키마. DB 값을 되돌릴 때 쓴다.
        session_factory: DB 세션을 만드는 함수. None이면 캐시 없이 클라이언트만 쓴다.
        clock: 현재 시각(UTC). 테스트용.
        monotonic: DB 건너뛰기 시간 계산용 시계. 테스트용.
    """

    USE_STALE_ON_ERROR = False

    def __init__(self, client, *, name: str, response_type: type[_R],
                 session_factory: Callable[[], Session] | None,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 monotonic: Callable[[], float] = time.monotonic):
        self._client = client
        self._name = name
        self._response_type = response_type
        self._session_factory = session_factory
        self._clock = clock
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._db_skip_until = 0.0

    @abstractmethod
    def _expires_at(self, now: datetime) -> datetime | None:
        """지금 받은 응답의 만료 시각. None이면 만료 없음."""

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
        if cached is not None and (cached.expires_at is None or cached.expires_at > now):
            return cached.response
        try:
            response = self._client.fetch_parsed(request)
        except Exception:
            if self.USE_STALE_ON_ERROR and cached is not None:
                logger.warning("%s 조회 실패 — 만료된 캐시로 대신함 (만료 %s)", self._name, cached.expires_at)
                return cached.response
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

    def _read(self, key: str) -> _Cached[_R] | None:
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
            return _Cached(self._response_type.model_validate(payload), expires_at)
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
            expires_at=self._expires_at(now),
        )
        try:
            with self._session_factory() as session:
                ApiResponseCacheRepository(session).put(entry)
                session.commit()
        except SQLAlchemyError as e:
            self._db_failed("저장", e)


class ScheduledFetcher(CachedFetcherBase[_R]):
    """미리 쌓아 두고 스케줄러가 주기적으로 점검하는 데이터용(법령·행정규칙 검색·본문).

    - Tool 조회(fetch_parsed): DB 값을 쓴다. 스케줄러가 멈춰 recheck_after가 지나면 직접 다시 받는다.
    - 클라이언트 호출이 실패하면 만료된 값이라도 쓴다(어제 버전 목록도 대부분 맞음).
    - 스케줄러 점검(refresh): DB를 보지 않고 새로 받아 덮어쓴다.

    Args:
        recheck_after: 점검 뒤 이 시간이 지나면 Tool 조회 때 다시 받는다. None이면 다시 받지 않는다(버전이 고정된 본문).
        **kwargs: CachedFetcherBase 인자.
    """

    USE_STALE_ON_ERROR = True

    def __init__(self, client, *, recheck_after: timedelta | None, **kwargs):
        super().__init__(client, **kwargs)
        self._recheck_after = recheck_after

    def _expires_at(self, now: datetime) -> datetime | None:
        return None if self._recheck_after is None else now + self._recheck_after

    def refresh(self, request: BaseModel) -> _R:
        """DB 값과 관계없이 새로 받아 저장한다. 스케줄러 점검용.

        Args:
            request: 클라이언트 요청 스키마.

        Returns:
            _R: 새로 받은 응답 스키마.

        Raises:
            Exception: 클라이언트 호출 실패. DB 값은 그대로 둔다.
        """
        response = self._client.fetch_parsed(request)
        self._write(request_key(request), request, response, self._clock())
        return response


class OnDemandFetcher(CachedFetcherBase[_R]):
    """무엇이 필요할지 미리 알 수 없어 조회할 때 쌓는 데이터용(관세청 확인기관).

    - 보관 시간 안이면 DB 값을, 지났거나 없으면 새로 받아 저장한다.
    - 클라이언트 호출이 실패하면 오류를 그대로 올린다(만료된 값으로 판정하지 않음).

    Args:
        ttl: 보관 시간.
        **kwargs: CachedFetcherBase 인자.
    """

    def __init__(self, client, *, ttl: timedelta, **kwargs):
        super().__init__(client, **kwargs)
        self._ttl = ttl

    def _expires_at(self, now: datetime) -> datetime | None:
        return now + self._ttl
