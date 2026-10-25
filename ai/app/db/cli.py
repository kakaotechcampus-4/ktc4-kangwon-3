"""AI DB 관리 명령.

    cd ai
    python -m app.db.cli init
"""

import argparse
import sys

from sqlalchemy.exc import OperationalError

from ..config import ConfigError
from .engine import init_db


def _init() -> int:
    """vector 확장과 테이블을 만들고 결과를 출력한다.

    Returns:
        int: 종료 코드. 0 성공, 2 설정 오류, 3 DB 연결 실패.
    """
    try:
        created = init_db()
    except ConfigError as exc:
        print(f"DB 설정 오류: {exc}", file=sys.stderr)
        return 2
    except OperationalError as exc:
        # 접속 문자열(비밀번호 포함)이 메시지에 섞일 수 있어 예외 타입만 남김
        print(f"DB 연결 실패 ({type(exc.orig).__name__})", file=sys.stderr)
        return 3
    print(f"새로 만든 테이블: {', '.join(created) if created else '없음 (모두 이미 있음)'}")
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
    args = parser.parse_args(argv)

    if args.command == "init":
        return _init()
    parser.error("알 수 없는 명령")


if __name__ == "__main__":
    sys.exit(main())
