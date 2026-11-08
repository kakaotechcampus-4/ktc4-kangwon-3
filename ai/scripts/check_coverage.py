"""커버리지 결과의 라인·분기 비율을 각각 기준과 비교한다. 하나라도 미달이면 종료 코드 1.

    python scripts/check_coverage.py coverage.json --line 95 --branch 90   (ai/ 에서 실행)

coverage.json은 pytest --cov --cov-report=json으로 만든다.
pytest-cov의 --cov-fail-under는 라인·분기를 합친 비율 하나만 봐서, BE(JaCoCo)처럼 따로 검사하려고 둠.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CoverageRates:
    """커버리지 비율 (%).

    Attributes:
        line: 라인 비율.
        branch: 분기 비율.
    """

    line: float
    branch: float


def _rate(covered: int, total: int) -> float:
    """비율(%)을 계산한다. 대상이 없으면 100.

    Args:
        covered: 실행된 수.
        total: 전체 수.

    Returns:
        float: 비율 (%).
    """
    return 100.0 if total == 0 else 100.0 * covered / total


def coverage_rates(report: dict) -> CoverageRates:
    """coverage.json 내용에서 라인·분기 비율을 읽는다.

    Args:
        report: coverage.json을 읽은 dict.

    Returns:
        CoverageRates: 라인·분기 비율.

    Raises:
        KeyError: totals 항목이 없는 경우 (분기 측정 없이 만든 결과 포함).
    """
    totals = report["totals"]
    return CoverageRates(
        line=_rate(totals["covered_lines"], totals["num_statements"]),
        branch=_rate(totals["covered_branches"], totals["num_branches"]),
    )


def shortfalls(rates: CoverageRates, min_line: float, min_branch: float) -> list[str]:
    """기준에 못 미친 항목을 문장으로 모은다.

    Args:
        rates: 측정한 비율.
        min_line: 라인 기준 (%).
        min_branch: 분기 기준 (%).

    Returns:
        list[str]: 미달 항목. 모두 기준 이상이면 빈 목록.
    """
    failed = []
    if rates.line < min_line:
        failed.append(f"라인 {rates.line:.2f}% < 기준 {min_line:g}%")
    if rates.branch < min_branch:
        failed.append(f"분기 {rates.branch:.2f}% < 기준 {min_branch:g}%")
    return failed


def main(argv: list[str] | None = None) -> int:
    """커버리지 결과 파일을 읽어 기준을 검사하고 결과를 출력한다.

    Args:
        argv: 명령줄 인자. None이면 sys.argv.

    Returns:
        int: 모두 기준 이상이면 0, 아니면 1.
    """
    parser = argparse.ArgumentParser(description="라인·분기 커버리지 기준 검사")
    parser.add_argument("report", type=Path, help="coverage.json 경로")
    parser.add_argument("--line", type=float, required=True, help="라인 기준 (%%)")
    parser.add_argument("--branch", type=float, required=True, help="분기 기준 (%%)")
    args = parser.parse_args(argv)

    rates = coverage_rates(json.loads(args.report.read_text(encoding="utf-8")))
    print(f"라인 {rates.line:.2f}% (기준 {args.line:g}%), 분기 {rates.branch:.2f}% (기준 {args.branch:g}%)")
    failed = shortfalls(rates, args.line, args.branch)
    for message in failed:
        print(f"커버리지 기준 미달: {message}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
