"""AI DB 관리 명령. 서버에서는 docker exec ai-app 으로 실행.

    cd ai
    python -m app.db.cli init
    python -m app.db.cli law-refresh
    python -m app.db.cli clear-cache law.text

종료 코드: 0 성공, 1 일부 실패, 2 설정 오류, 3 DB 연결 실패.
"""

import argparse
import sys
from collections.abc import Callable

from sqlalchemy.exc import OperationalError

from ..config import ConfigError, get_settings
from .engine import get_session_factory, init_db
from .law_cache import build_law_fetchers, refresh_laws
from .repositories.api_response_cache import ApiResponseCacheRepository


def _with_db(command: Callable[[], int]) -> int:
    """명령을 실행하고, DB 설정·연결 오류를 종료 코드로 바꾼다.

    Args:
        command: 실행할 명령. 종료 코드를 돌려준다.

    Returns:
        int: 종료 코드.
    """
    try:
        return command()
    except ConfigError as exc:
        print(f"DB 설정 오류: {exc}", file=sys.stderr)
        return 2
    except OperationalError as exc:
        # 접속 문자열(비밀번호 포함)이 메시지에 섞일 수 있어 예외 타입만 남김
        print(f"DB 연결 실패 ({type(exc.orig).__name__})", file=sys.stderr)
        return 3


def _init() -> int:
    """vector 확장과 테이블을 만들고 결과를 출력한다.

    Returns:
        int: 종료 코드.
    """
    created = init_db()
    print(f"새로 만든 테이블: {', '.join(created) if created else '없음 (모두 이미 있음)'}")
    return 0


def _law_refresh() -> int:
    """근거 문서의 현행·시행예정 버전 목록과 본문을 지금 바로 새로 받는다.

    Returns:
        int: 종료 코드. 실패한 문서가 있으면 1.
    """
    # 근거 문서 목록은 Tool 쪽에 있음. CLI는 서버 진입점이라 여기서만 가져옴
    from ..tools.common.law_sources import LAW_SOURCES

    # 조회 객체는 DB 연결 실패를 조용히 건너뛰므로 연결부터 확인
    init_db()
    fetchers = build_law_fetchers(get_settings().law_oc, get_session_factory())
    try:
        report = refresh_laws(fetchers, LAW_SOURCES)
    finally:
        fetchers.close()
    print(f"법령 점검 — 문서 {report.checked}개, 버전 {report.versions}개, 실패 {', '.join(report.failed) or '없음'}")
    return 1 if report.failed else 0


def _clear_cache(client: str) -> int:
    """한 클라이언트의 캐시를 모두 지운다. 다음 조회 때 새로 받는다.

    Args:
        client: 클라이언트 캐시 이름(예: "law.text").

    Returns:
        int: 종료 코드.
    """
    init_db()
    with get_session_factory()() as session:
        deleted = ApiResponseCacheRepository(session).delete_by_client(client)
        session.commit()
    print(f"{client} 캐시 {deleted}건 삭제")
    return 0


def main(argv: list[str] | None = None) -> int:
    """명령을 해석해 실행한다.

    Args:
        argv: 명령 인자. None이면 sys.argv를 쓴다.

    Returns:
        int: 종료 코드.
    """
    parser = argparse.ArgumentParser(prog="python -m app.db.cli", description="AI DB 관리 명령")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="vector 확장과 테이블 생성 (이미 있으면 건너뜀)")
    commands.add_parser("law-refresh", help="근거 법령·행정규칙의 현행·시행예정 버전을 지금 새로 받음")
    clear = commands.add_parser("clear-cache", help="한 클라이언트의 응답 캐시를 모두 삭제")
    clear.add_argument("client", help='캐시 이름 (예: "law.text", "law.eflaw_search", "admrul.search")')
    args = parser.parse_args(argv)

    if args.command == "init":
        return _with_db(_init)
    if args.command == "law-refresh":
        return _with_db(_law_refresh)
    if args.command == "clear-cache":
        return _with_db(lambda: _clear_cache(args.client))
    parser.error("알 수 없는 명령")


if __name__ == "__main__":
    sys.exit(main())
