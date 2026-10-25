"""DB 우선 조회 객체가 클라이언트를 직접 부른 것과 같은 결과를 내는지 DB 없이 검증한다."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError

from app.tools.common import cached_fetcher
from app.tools.common.cached_fetcher import CachedFetcher, request_key

NOW = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


class _Request(BaseModel):
    mst: str
    display: int = 20


class _Item(BaseModel):
    name: str
    enforce_date: str | None = None


class _Response(BaseModel):
    total: int
    items: list[_Item]


class _Client:
    def __init__(self, error: Exception | None = None):
        self.calls: list[_Request] = []
        self.error = error
        self.closed = False

    def fetch_parsed(self, request: _Request) -> _Response:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return _Response(total=1, items=[_Item(name=f"문서 {request.mst}", enforce_date="20261101")])

    def close(self):
        self.closed = True


class _Db:
    """DB 대신 쓰는 dict 저장소와 세션 팩토리. fail을 켜면 세션 사용이 DB 오류로 끝난다."""

    def __init__(self):
        self.rows: dict[tuple[str, str], SimpleNamespace] = {}
        self.sessions = 0
        self.commits = 0
        self.fail = False

    def session_factory(self):
        self.sessions += 1
        db = self

        class _Session:
            def __enter__(self):
                if db.fail:
                    raise OperationalError("connect", {}, ConnectionRefusedError())
                return self

            def __exit__(self, *exc):
                return False

            def commit(self):
                db.commits += 1

        session = _Session()
        session.db = db
        return session


class _Repository:
    def __init__(self, session):
        self._rows = session.db.rows

    def get(self, client, key):
        return self._rows.get((client, key))

    def put(self, entry):
        self._rows[(entry.client, entry.request_key)] = SimpleNamespace(
            request=entry.request, response=entry.response, expires_at=entry.expires_at)


@pytest.fixture
def db(monkeypatch) -> _Db:
    monkeypatch.setattr(cached_fetcher, "ApiResponseCacheRepository", _Repository)
    return _Db()


class _Clock:
    def __init__(self):
        self.now = NOW
        self.seconds = 0.0

    def advance(self, seconds: float):
        self.now += timedelta(seconds=seconds)
        self.seconds += seconds


def _fetcher(client, db, clock=None, *, ttl=timedelta(days=1), **kwargs) -> CachedFetcher:
    clock = clock or _Clock()
    return CachedFetcher(client, name="law.search", response_type=_Response, ttl=ttl,
                         session_factory=db.session_factory if db else None,
                         clock=lambda: clock.now, monotonic=lambda: clock.seconds, **kwargs)


def test_DB에_없으면_클라이언트로_받아_저장하고_그대로_돌려준다(db):
    client = _Client()

    response = _fetcher(client, db).fetch_parsed(_Request(mst="1"))

    assert response == _Response(total=1, items=[_Item(name="문서 1", enforce_date="20261101")])
    row = db.rows[("law.search", request_key(_Request(mst="1")))]
    assert row.request == {"mst": "1", "display": 20}
    assert row.response == response.model_dump(mode="json")
    assert row.expires_at == NOW + timedelta(days=1)
    assert db.commits == 1


def test_DB에_있으면_클라이언트를_부르지_않고_직접_부른_결과와_같은_값을_돌려준다(db):
    first = _Client()
    _fetcher(first, db).fetch_parsed(_Request(mst="1"))
    second = _Client()

    response = _fetcher(second, db).fetch_parsed(_Request(mst="1"))

    assert second.calls == []
    assert response == first.fetch_parsed(_Request(mst="1"))
    assert type(response) is _Response


def test_요청이_다르면_따로_저장한다(db):
    fetcher = _fetcher(_Client(), db)

    fetcher.fetch_parsed(_Request(mst="1"))
    fetcher.fetch_parsed(_Request(mst="1", display=100))

    assert len(db.rows) == 2


def test_만료되면_다시_받아_덮어쓴다(db):
    clock = _Clock()
    client = _Client()
    fetcher = _fetcher(client, db, clock)
    fetcher.fetch_parsed(_Request(mst="1"))

    clock.advance(timedelta(days=1).total_seconds() + 1)
    fetcher.fetch_parsed(_Request(mst="1"))

    assert len(client.calls) == 2
    (row,) = db.rows.values()
    assert row.expires_at == clock.now + timedelta(days=1)


def test_보관_시간이_없으면_영구_보관한다(db):
    clock = _Clock()
    client = _Client()
    fetcher = _fetcher(client, db, clock, ttl=None)
    fetcher.fetch_parsed(_Request(mst="1"))

    clock.advance(timedelta(days=365).total_seconds())
    fetcher.fetch_parsed(_Request(mst="1"))

    assert len(client.calls) == 1
    (row,) = db.rows.values()
    assert row.expires_at is None


def test_조회_실패_때_허용하면_만료된_DB_값으로_대신한다(db):
    clock = _Clock()
    _fetcher(_Client(), db, clock).fetch_parsed(_Request(mst="1"))
    clock.advance(timedelta(days=2).total_seconds())

    fetcher = _fetcher(_Client(error=TimeoutError()), db, clock, use_stale_on_error=True)

    response = fetcher.fetch_parsed(_Request(mst="1"))

    assert response.items[0].name == "문서 1"


def test_조회_실패_때_허용하지_않으면_만료된_값이_있어도_오류를_올린다(db):
    clock = _Clock()
    _fetcher(_Client(), db, clock).fetch_parsed(_Request(mst="1"))
    clock.advance(timedelta(days=2).total_seconds())

    with pytest.raises(TimeoutError):
        _fetcher(_Client(error=TimeoutError()), db, clock).fetch_parsed(_Request(mst="1"))


def test_DB에_값이_없으면_허용해도_조회_오류를_올린다(db):
    with pytest.raises(TimeoutError):
        _fetcher(_Client(error=TimeoutError()), db, use_stale_on_error=True).fetch_parsed(_Request(mst="1"))
    assert db.rows == {}


def test_저장된_값이_지금_응답_스키마와_맞지_않으면_다시_받아_덮어쓴다(db):
    key = request_key(_Request(mst="1"))
    db.rows[("law.search", key)] = SimpleNamespace(request={}, response={"total": "많음"}, expires_at=None)
    client = _Client()

    response = _fetcher(client, db).fetch_parsed(_Request(mst="1"))

    assert len(client.calls) == 1
    assert db.rows[("law.search", key)].response == response.model_dump(mode="json")


def test_DB가_없으면_클라이언트만_쓴다():
    client = _Client()
    fetcher = _fetcher(client, None)

    fetcher.fetch_parsed(_Request(mst="1"))
    fetcher.fetch_parsed(_Request(mst="1"))

    assert len(client.calls) == 2


def test_DB_실패_뒤_일정_시간은_DB를_건너뛰고_지나면_다시_쓴다(db, monkeypatch):
    monkeypatch.setattr(cached_fetcher, "CACHE_DB_RETRY_SECONDS", 60)
    clock = _Clock()
    client = _Client()
    fetcher = _fetcher(client, db, clock)
    db.fail = True

    assert fetcher.fetch_parsed(_Request(mst="1")).items[0].name == "문서 1"
    fetcher.fetch_parsed(_Request(mst="1"))
    assert db.sessions == 1
    assert len(client.calls) == 2

    db.fail = False
    clock.advance(60)
    fetcher.fetch_parsed(_Request(mst="1"))
    assert db.sessions == 3
    assert len(db.rows) == 1


def test_요청_키는_같은_요청이면_같고_64자다():
    assert request_key(_Request(mst="1")) == request_key(_Request(display=20, mst="1"))
    assert request_key(_Request(mst="1")) != request_key(_Request(mst="2"))
    assert len(request_key(_Request(mst="1"))) == 64


def test_close는_클라이언트를_닫는다(db):
    client = _Client()

    _fetcher(client, db).close()

    assert client.closed is True
