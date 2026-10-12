"""별표 파싱 출력을 정답셋과 대조해 채점. 모델 없이 도는 순수 함수만 둠.

행은 (번호, 품목명)으로 짝짓고, 짝지은 행의 분류·문구 칸을 비교함.
비교는 테두리 문자·공백을 뺀 글자로 함(원문 대조와 같은 기준).
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ..schemas.agents.annex import AnnexItem, AnnexParseOutput
from ..utils.annex_check import normalize

ANNEX_TRUTH_DIR = Path(__file__).resolve().parents[2] / "tests" / "eval_truth_annex"


@dataclass
class AnnexScore:
    """별표 하나의 채점 결과.

    Attributes:
        expected_rows: 정답 행 수.
        actual_rows: 출력 행 수.
        matched_rows: (번호, 품목명)이 맞는 행 수.
        missing: 출력에 없는 정답 행.
        extra: 정답에 없는 출력 행.
        category_errors: 짝지은 행 중 분류가 다른 행.
        field_errors: 짝지은 행 중 한정·제외·포함·추가 칸이 다른 행.
        scheme_ok: 규제 구분 일치 여부.
        skipped_ok: 뺀 행 목록 일치 여부.
        notes_ok: 표 전체 비고 일치 여부.
    """

    expected_rows: int
    actual_rows: int
    matched_rows: int = 0
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    category_errors: list[str] = field(default_factory=list)
    field_errors: list[str] = field(default_factory=list)
    scheme_ok: bool = True
    skipped_ok: bool = True
    notes_ok: bool = True


def load_annex_truth(path: Path) -> tuple[str, AnnexParseOutput]:
    """정답 파일을 읽는다.

    Returns:
        tuple[str, AnnexParseOutput]: (픽스처 디렉터리 이름, 정답 출력).
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["fixture"], AnnexParseOutput.model_validate(data["output"])


def _key(item: AnnexItem) -> tuple[str, str]:
    return normalize(item.item_label or ""), normalize(item.item_name)


def _describe(item: AnnexItem) -> str:
    return " > ".join([*item.category_path, f"{item.item_label or ''} {item.item_name}".strip()])


def _texts(values: list[str]) -> Counter:
    return Counter(normalize(value) for value in values)


def _fields(item: AnnexItem) -> tuple:
    return (
        _texts(item.conditions),
        _texts(item.exclusions),
        _texts(item.inclusions),
        Counter((normalize(attribute.name), normalize(attribute.value)) for attribute in item.attributes),
    )


def score_annex(expected: AnnexParseOutput, actual: AnnexParseOutput) -> AnnexScore:
    """출력을 정답과 비교한다. 같은 (번호, 품목명)이 여러 번이면 원문 순서대로 짝지음.

    Args:
        expected: 정답.
        actual: 에이전트 출력.

    Returns:
        AnnexScore: 행 단위 일치·누락·초과와 칸별 오류.
    """
    score = AnnexScore(expected_rows=len(expected.items), actual_rows=len(actual.items))
    remaining = list(actual.items)
    for item in expected.items:
        match = next((candidate for candidate in remaining if _key(candidate) == _key(item)), None)
        if match is None:
            score.missing.append(_describe(item))
            continue
        remaining.remove(match)
        score.matched_rows += 1
        if [normalize(part) for part in match.category_path] != [normalize(part) for part in item.category_path]:
            score.category_errors.append(f"{_describe(item)} ← {_describe(match)}")
        if _fields(match) != _fields(item):
            score.field_errors.append(_describe(item))
    score.extra = [_describe(item) for item in remaining]
    score.scheme_ok = normalize(expected.scheme) == normalize(actual.scheme)
    score.skipped_ok = (Counter((normalize(row.item_label or ""), normalize(row.reason)) for row in expected.skipped)
                        == Counter((normalize(row.item_label or ""), normalize(row.reason)) for row in actual.skipped))
    score.notes_ok = _texts(expected.notes) == _texts(actual.notes)
    return score
