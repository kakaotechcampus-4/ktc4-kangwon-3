"""검증 에이전트 단독 실행.

    cd ai
    python -m app.verify_cli examples/verification_draft.json --rules-only
    python -m app.verify_cli examples/verification_draft.json
"""

import argparse
import json
import sys
from pathlib import Path

from .agents.verification import VerificationAgent, VerificationError
from .schemas.schemas import DraftAssessment, TraceEvent


def main() -> int:
    # Windows 기본 콘솔 인코딩(cp949)으로는 한글 출력이 깨지거나 실패한다.
    # 리다이렉트한 결과 파일도 UTF-8이어야 다른 도구가 읽을 수 있다.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="검증 에이전트 단독 실행")
    parser.add_argument("input", type=Path, help="DraftAssessment JSON 파일")
    parser.add_argument(
        "--rules-only",
        action="store_true",
        help="API 호출 없이 구조 검사만 수행한다. 전체 검증이 아니다.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="스키마 변환과 실행 단계 trace를 표준 오류에 JSON으로 출력한다.",
    )
    args = parser.parse_args()
    trace: list[TraceEvent] | None = [] if args.trace else None

    try:
        draft = DraftAssessment.model_validate_json(args.input.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        # 입력 문제와 호출 문제를 구분해서 알린다.
        print(f"입력 JSON을 읽지 못했습니다: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    try:
        if args.rules_only:
            result = VerificationAgent().verify_rules(draft, trace=trace)
        else:
            result = VerificationAgent.from_env().verify(draft, trace=trace)
    except VerificationError as exc:
        _print_trace(trace)
        print(f"검증 미완료: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        # 설정 오류(ConfigError 등)를 원인과 함께 그대로 보여준다.
        print(f"실행 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    _print_trace(trace)
    print(result.model_dump_json(indent=2))
    if args.rules_only:
        print(
            "\n[주의] --rules-only는 구조 검사만 한 결과입니다. 검증 완료로 쓰지 마세요.",
            file=sys.stderr,
        )
    return 0



def _print_trace(trace: list[TraceEvent] | None) -> None:
    if trace is None:
        return
    payload = [event.model_dump(mode="json") for event in trace]
    print("[trace]", file=sys.stderr)
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
