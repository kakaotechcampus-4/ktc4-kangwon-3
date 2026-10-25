"""DB 관리 명령(python -m app.repositories.cli)의 출력과 종료 코드를 DB 없이 검증한다."""

import pytest
from sqlalchemy.exc import OperationalError

from app.repositories import cli
from app.repositories.errors import DatabaseNotConfiguredError


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
