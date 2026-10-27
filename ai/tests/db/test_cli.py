"""DB 관리 명령(python -m app.db.cli)의 출력과 종료 코드를 DB 없이 검증한다."""

import pytest
from sqlalchemy.exc import OperationalError

from app.db import cli
from app.db.errors import DatabaseNotConfiguredError


def _raise(exc):
    def fail():
        raise exc
    return fail


def test_init은_새로_만든_테이블을_출력한다(monkeypatch, capsys):
    monkeypatch.setattr(cli, "init_db", lambda: ["api_response_cache", "hs_cases"])

    assert cli.main(["init"]) == 0
    assert capsys.readouterr().out == "새로 만든 테이블: api_response_cache, hs_cases\n"


def test_init은_모두_있으면_없음으로_알린다(monkeypatch, capsys):
    monkeypatch.setattr(cli, "init_db", lambda: [])

    assert cli.main(["init"]) == 0
    assert "없음 (모두 이미 있음)" in capsys.readouterr().out


def test_DATABASE_URL이_없으면_설정_오류로_끝난다(monkeypatch, capsys):
    monkeypatch.setattr(cli, "init_db", _raise(DatabaseNotConfiguredError("DATABASE_URL이 설정되지 않음")))

    assert cli.main(["init"]) == 2
    assert "DB 설정 오류: DATABASE_URL이 설정되지 않음" in capsys.readouterr().err


def test_DB_연결_실패는_비밀번호_없이_예외_타입만_알린다(monkeypatch, capsys):
    error = OperationalError("connect", {}, ConnectionRefusedError("postgresql://ai:secret-password@db/ai"))
    monkeypatch.setattr(cli, "init_db", _raise(error))

    assert cli.main(["init"]) == 3
    err = capsys.readouterr().err
    assert "DB 연결 실패 (ConnectionRefusedError)" in err
    assert "secret-password" not in err


@pytest.mark.parametrize("argv", [[], ["drop"]])
def test_명령이_없거나_모르는_명령이면_사용법_오류로_끝난다(argv):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(argv)

    assert exc_info.value.code == 2


class _Fetchers:
    closed = False

    def close(self):
        self.closed = True


def _law_refresh(monkeypatch, report=None, error=None) -> _Fetchers:
    """DB 준비·조회 객체를 가짜로 바꾸고, 법령 점검 결과(또는 예외)를 정한다."""
    from app.db.law_cache import LawRefreshReport

    fetchers = _Fetchers()
    monkeypatch.setattr(cli, "init_db", lambda: [])
    monkeypatch.setattr(cli, "get_session_factory", lambda: "session-factory")
    monkeypatch.setattr(cli, "build_law_fetchers", lambda oc, factory: fetchers)

    def refresh(f, sources):
        if error is not None:
            raise error
        return report or LawRefreshReport(checked=len(sources), versions=7, failed=[])
    monkeypatch.setattr(cli, "refresh_laws", refresh)
    monkeypatch.setattr(cli, "get_settings", lambda: type("S", (), {"law_oc": "test-oc"})())
    return fetchers


def test_law_refresh는_점검_결과를_출력하고_조회_객체를_닫는다(monkeypatch, capsys):
    fetchers = _law_refresh(monkeypatch)

    assert cli.main(["law-refresh"]) == 0
    from app.tools.common.law_sources import LAW_SOURCES

    assert f"법령 점검 — 문서 {len(LAW_SOURCES)}개, 버전 7개, 실패 없음" in capsys.readouterr().out
    assert fetchers.closed is True


def test_law_refresh는_실패한_문서가_있으면_1로_끝난다(monkeypatch, capsys):
    from app.db.law_cache import LawRefreshReport

    _law_refresh(monkeypatch, report=LawRefreshReport(checked=5, versions=5, failed=["전파법"]))

    assert cli.main(["law-refresh"]) == 1
    assert "실패 전파법" in capsys.readouterr().out


def test_law_refresh_도중_예외가_나도_조회_객체를_닫는다(monkeypatch):
    fetchers = _law_refresh(monkeypatch, error=RuntimeError("점검 실패"))

    with pytest.raises(RuntimeError):
        cli.main(["law-refresh"])
    assert fetchers.closed is True


def test_law_refresh는_DB_연결이_안_되면_점검하지_않는다(monkeypatch, capsys):
    built = []
    monkeypatch.setattr(cli, "init_db", _raise(OperationalError("connect", {}, ConnectionRefusedError())))
    monkeypatch.setattr(cli, "build_law_fetchers", lambda *args: built.append(args))

    assert cli.main(["law-refresh"]) == 3
    assert built == []


class _Session:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def commit(self):
        self.committed = True


def test_clear_cache는_그_클라이언트_캐시를_지우고_건수를_출력한다(monkeypatch, capsys):
    session = _Session()
    deleted = []

    class _Repository:
        def __init__(self, s):
            assert s is session

        def delete_by_client(self, client):
            deleted.append(client)
            return 4

    monkeypatch.setattr(cli, "init_db", lambda: [])
    monkeypatch.setattr(cli, "get_session_factory", lambda: lambda: session)
    monkeypatch.setattr(cli, "ApiResponseCacheRepository", _Repository)

    assert cli.main(["clear-cache", "law.text"]) == 0
    assert deleted == ["law.text"]
    assert session.committed is True
    assert capsys.readouterr().out == "law.text 캐시 4건 삭제\n"


def test_clear_cache는_캐시_이름이_없으면_사용법_오류로_끝난다():
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["clear-cache"])

    assert exc_info.value.code == 2


class _Client:
    closed = False

    def close(self):
        self.closed = True


def _clip_ingest(monkeypatch, report=None, error=None) -> dict:
    """DB 준비·클라이언트·적재 루틴을 가짜로 바꾸고, 적재 루틴이 받은 인자를 기록한다."""
    from app.db.clip_ingest import ClipIngestReport

    called = {"search": _Client(), "detail": _Client()}
    monkeypatch.setattr(cli, "init_db", lambda: [])
    monkeypatch.setattr(cli, "get_session_factory", lambda: "session-factory")
    monkeypatch.setattr(cli, "CLIPClient", lambda: called["search"])
    monkeypatch.setattr(cli, "CLIPDetailClient", lambda: called["detail"])
    settings = type("Settings", (), {"embedding_model": "openai/text-embedding-3-small"})()
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    def ingest(**kwargs):
        called["kwargs"] = kwargs
        if error is not None:
            raise error
        return report or ClipIngestReport(listed=54303, existing=13679, saved=40624)
    monkeypatch.setattr(cli, "ingest_clip_cases", ingest)
    return called


def test_clip_ingest는_적재_결과를_출력하고_클라이언트를_닫는다(monkeypatch, capsys):
    called = _clip_ingest(monkeypatch)

    assert cli.main(["clip-ingest"]) == 0
    assert "CLIP 적재 — 목록 54303건, 이미 있음 13679건, 새로 저장 40624건, 실패 없음" in capsys.readouterr().out
    kwargs = called["kwargs"]
    assert (kwargs["search"], kwargs["detail"]) == (called["search"], called["detail"])
    assert (kwargs["workers"], kwargs["limit"], kwargs["raw_dir"]) == (4, None, None)
    assert kwargs["embedding_model"] == "openai/text-embedding-3-small"
    assert kwargs["session_factory"] == "session-factory"
    assert called["search"].closed and called["detail"].closed


def test_clip_ingest는_동시_요청_수·시험_적재_건수·원문_폴더를_받는다(monkeypatch, tmp_path):
    called = _clip_ingest(monkeypatch)

    cli.main(["clip-ingest", "--workers", "2", "--limit", "200", "--raw-dir", str(tmp_path)])

    assert (called["kwargs"]["workers"], called["kwargs"]["limit"], called["kwargs"]["raw_dir"]) == (2, 200, tmp_path)


def test_clip_ingest는_실패한_사례가_있으면_앞_10건만_보이고_1로_끝난다(monkeypatch, capsys):
    from app.db.clip_ingest import ClipIngestReport

    failed = [str(n) for n in range(12)]
    _clip_ingest(monkeypatch, report=ClipIngestReport(listed=12, saved=0, failed=failed))

    assert cli.main(["clip-ingest"]) == 1
    assert "실패 12건 (0, 1, 2, 3, 4, 5, 6, 7, 8, 9 …)" in capsys.readouterr().out


def test_clip_ingest_도중_예외가_나도_클라이언트를_닫는다(monkeypatch):
    called = _clip_ingest(monkeypatch, error=RuntimeError("CLIP 목록 3페이지가 비어 있습니다."))

    with pytest.raises(RuntimeError):
        cli.main(["clip-ingest"])
    assert called["search"].closed and called["detail"].closed
