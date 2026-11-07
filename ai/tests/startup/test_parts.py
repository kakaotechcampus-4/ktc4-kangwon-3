"""운영 부품(production_parts)이 파이프라인·DB·법령 점검·BE 콜백 전송을 제대로 만드는지 확인한다.

서버는 띄우지 않고 함수를 직접 부름. 바깥 연결(파이프라인 조립·DB·법령 조회)만 기록용으로 바꿈.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from app import config
from app.clients.backend import SendResult
from app.db import LawChange, LawChangeKind, LawVersion
from app.diagnosis import build_questions
from app.routers import _dummy
from app.startup import parts as startup
from tests.app_harness import app_env


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    yield from app_env(monkeypatch)


class _LawFetchers:
    closed = False

    def close(self):
        self.closed = True


class _LawChangeSender:
    """받은 설정과 변경 묶음을 기록하는 가짜 BE 전송."""

    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token
        self.requests = []
        self.closed = False

    def send(self, request):
        self.requests.append(request)
        return SendResult(200, "OK")

    def close(self):
        self.closed = True


@pytest.fixture
def production(monkeypatch):
    """운영 부품 만들기의 바깥 연결을 기록용으로 바꿈.

    Returns:
        SimpleNamespace: build(설정으로 운영 부품을 만들고 콜백 전송을 닫음), jobs(파이프라인 조립 인자),
            fetchers(법령 조회), refreshed(법령 점검·캐시 정리 호출), law_options(법령 조회 생성 옵션),
            refresh(예약 작업에 넘긴 점검 함수), law_change_senders(법령 변경 전송).
    """
    recorded = SimpleNamespace(jobs=[], fetchers=_LawFetchers(), refreshed=[], law_options=[], refresh=[],
                               law_change_senders=[])

    def law_change_sender(base_url, token):
        recorded.law_change_senders.append(_LawChangeSender(base_url, token))
        return recorded.law_change_senders[-1]

    monkeypatch.setattr(startup, "BackendLawChangeClient", law_change_sender)
    monkeypatch.setattr(startup, "build_parts", lambda: "pipeline-parts")
    monkeypatch.setattr(startup, "build_job", lambda parts, questions: recorded.jobs.append((parts, questions))
                        or _dummy.run_dummy_diagnosis)
    monkeypatch.setattr(startup, "get_session_factory", lambda: "session-factory")
    monkeypatch.setattr(startup, "build_law_fetchers",
                        lambda oc, factory, **kwargs: recorded.law_options.append(kwargs) or recorded.fetchers)
    monkeypatch.setattr(startup, "refresh_laws",
                        lambda f, sources, **kwargs: recorded.refreshed.append((f, sources, kwargs)))
    monkeypatch.setattr(startup, "purge_expired_responses",
                        lambda factory, clients: recorded.refreshed.append((factory, clients)))
    # 예약 작업은 돌리지 않고 넘긴 점검 함수만 받아 둠
    monkeypatch.setattr(startup, "run_law_refresh", recorded.refresh.append)
    monkeypatch.setattr(startup, "SessionArchiveDatabase", lambda factory: SimpleNamespace(factory=factory))

    def build() -> startup.AppParts:
        parts = startup.production_parts(config.get_settings())
        parts.callback_sender.close()
        return parts

    recorded.build = build
    return recorded


def _init_db(monkeypatch, created=()) -> None:
    monkeypatch.setattr(startup, "init_db", lambda: list(created))


def test_운영_부품은_파이프라인을_한_번_조립해_운영_진단_함수로_쓴다(production):
    production.build()

    assert production.jobs == [("pipeline-parts", build_questions)]


def test_운영_부품은_DB_테이블을_만들고_새로_만든_테이블을_로그로_남긴다(production, monkeypatch, caplog):
    _init_db(monkeypatch, created=["api_response_cache", "hs_cases"])

    with caplog.at_level("INFO", logger="app.startup.parts"):
        parts = production.build()

    assert "DB 준비 완료 (새로 만든 테이블: api_response_cache, hs_cases)" in caplog.text
    assert parts.database.archive.factory == "session-factory"


def test_운영_부품의_법령_점검은_근거_문서를_받고_캐시를_정리하며_정리_때_조회_객체를_닫는다(production, monkeypatch):
    _init_db(monkeypatch)
    database = production.build().database

    database.background[0]()
    [refresh] = production.refresh
    refresh()
    database.close()

    [(fetchers, sources, options), purged] = production.refreshed
    assert (fetchers, sources, options["select"]) == (production.fetchers, startup.LAW_SOURCES, startup.applied_version)
    assert purged == ("session-factory", ["customs.gw"])
    assert production.fetchers.closed is True


def _refresh_on_change(production, database):
    """예약 작업을 한 번 돌려 법령 점검에 넘긴 on_change를 꺼낸다."""
    database.background[0]()
    production.refresh[0]()
    return production.refreshed[0][2]["on_change"]


def test_법령_점검이_찾은_변경은_로그로_남기고_적용_판_변경만_BE로_보낸다(production, monkeypatch, caplog):
    _init_db(monkeypatch)
    on_change = _refresh_on_change(production, production.build().database)
    version = LawVersion("291321", "20261020", "20260420", "일부개정")
    source = ("어린이제품 안전 특별법 시행규칙", "012345", False, "children_product_safety", version)

    with caplog.at_level("INFO", logger="app.db.law_changes"):
        on_change([LawChange(LawChangeKind.APPLIED, *source, "280000"), LawChange(LawChangeKind.SKIPPED, *source)])

    [sender] = production.law_change_senders
    [request] = sender.requests
    assert [(change.serial_number, change.previous_serial_number) for change in request.changes] == [
        ("291321", "280000")]
    assert ("applied" in caplog.text, "skipped" in caplog.text) == (True, True)


def test_법령_변경_전송은_BE_주소와_내부_토큰을_쓰고_정리_때_닫는다(production, monkeypatch):
    _init_db(monkeypatch)
    settings = config.get_settings()

    database = production.build().database
    database.close()

    [sender] = production.law_change_senders
    assert (sender.base_url, sender.token) == (settings.be_base_url, settings.internal_api_token)
    assert sender.closed is True


def test_법령_점검용_조회_객체는_캐시_조회를_측정_기록으로_남기지_않는다(production, monkeypatch):
    _init_db(monkeypatch)

    production.build()

    assert production.law_options == [{"measure": False}]


def test_DATABASE_URL이_없으면_DB_부품_없이_만들고_법령_조회도_만들지_않는다(production, caplog):
    with caplog.at_level("WARNING", logger="app.startup.parts"):
        parts = production.build()

    assert parts.database is None
    assert production.law_options == []
    assert "DATABASE_URL 미설정" in caplog.text


def test_DB_준비에_실패해도_경고만_남기고_DB_부품_없이_만든다(production, monkeypatch, caplog):
    def fail():
        raise OperationalError("connect", {}, ConnectionRefusedError("거부됨"))
    monkeypatch.setattr(startup, "init_db", fail)

    with caplog.at_level("WARNING", logger="app.startup.parts"):
        parts = production.build()

    assert parts.database is None
    assert "DB 준비 실패" in caplog.text
