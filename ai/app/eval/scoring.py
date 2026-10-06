"""정답표(truth JSON)와 N회 실행 결과를 대조해 리포트를 만든다.

한 번만 돌려서 채점하면 안 된다. temperature=0에서도 같은 입력이 다른 답을
내는 것이 실측으로 확인됐다(docs/EXTRACTION_EVAL.md 0절). 그래서 이 모듈은
항상 여러 번의 실행 결과를 함께 받는다.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..schemas.product import ProductAttributes
from .grading import (
    Grade,
    attribute_names_for,
    grade_attribute_value,
    Stability,
    classify_stability,
    grade_boolean,
    grade_forbidden_items,
    grade_keywords,
    grade_required_items,
    grade_verbatim,
    is_hard_flip,
)


@dataclass(frozen=True)
class FieldReport:
    """필드 하나의 N회 채점 결과."""

    name: str
    truth: Any
    values: list[Any]
    grades: list[Grade]
    stability: Stability
    hard_flip: bool
    evidence: str | None = None

    @property
    def worst(self) -> Grade:
        """가장 나쁜 등급. C1 > C3 > C2 > OK 순으로 본다."""
        order = {Grade.C1: 3, Grade.C3: 2, Grade.C2: 1, Grade.OK: 0}
        return max(self.grades, key=lambda g: order[g])


@dataclass
class FixtureReport:
    """픽스처 하나의 전체 채점 결과."""

    fixture: str
    runs: int
    fields: list[FieldReport] = field(default_factory=list)
    # 정답표에 기준이 없어 채점하지 않은 필드. 커버리지를 속이지 않으려고 남긴다.
    ungraded: list[str] = field(default_factory=list)
    # listing_text 채점은 counts()에 넣지 않고 따로 둔다. 넣으면 분모가 늘어 아무것도
    # 안 고쳤는데 C1 비율이 내려가 보이고, 이전 측정치와 비교할 수 없게 된다.
    listing_fields: list[FieldReport] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        """등급·안정성별 필드 수. 분모는 '채점한 필드 수'다."""
        graded = self.fields
        return {
            "graded_fields": len(graded),
            "ungraded_fields": len(self.ungraded),
            "c1": sum(1 for f in graded if f.worst is Grade.C1),
            "c2": sum(1 for f in graded if f.worst is Grade.C2),
            "c3": sum(1 for f in graded if f.worst is Grade.C3),
            "stable_ok": sum(1 for f in graded if f.stability is Stability.STABLE_OK),
            "stable_wrong": sum(1 for f in graded if f.stability is Stability.STABLE_WRONG),
            "unstable": sum(1 for f in graded if f.stability is Stability.UNSTABLE),
            "hard_flip": sum(1 for f in graded if f.hard_flip),
        }

    def listing_counts(self) -> dict[str, int]:
        """listing_text 항목별 등급. 놓친 판매자 문구(C1)와 섞인 문구(C3)를 나눠 센다."""
        return {
            "items": len(self.listing_fields),
            "c1_missing": sum(1 for f in self.listing_fields if f.worst is Grade.C1),
            "c3_mixed": sum(1 for f in self.listing_fields if f.worst is Grade.C3),
            # 항목 수만 보면 "한 번 크게 섞였는지, 매번 조금씩 섞였는지"를 구분할 수 없다.
            # 반복 실행에서 오염이 얼마나 자주 일어나는지는 회차 단위로 본다.
            "runs_mixed": sum(
                1
                for index in range(self.runs)
                if any(f.grades[index] is Grade.C3 for f in self.listing_fields)
            ),
        }


# 모델이 만들지 않고 시스템이 채우는 값이라 채점 대상이 아니다.
_NEVER_GRADED = {"product_id", "source_url"}

_PRODUCT_FIELDS = set(ProductAttributes.model_fields)
_BOOLEAN_FIELDS = {
    name
    for name, info in ProductAttributes.model_fields.items()
    if info.annotation == (bool | None)
}


def check_truth(truth: dict) -> None:
    """정답표가 실제 스키마와 맞는지 본다.

    필드명에 오타가 있으면 그 필드는 모델 출력에서 항상 None으로 읽혀 "정답"으로
    채점된다. 조용히 통과하면서 측정값만 오염시키므로 채점 전에 막는다.
    """
    unknown: list[str] = []
    for section in ("booleans", "verbatim", "keywords"):
        unknown += [
            f"{section}.{name}"
            for name in (truth.get(section) or {})
            if name not in _PRODUCT_FIELDS
        ]
    if unknown:
        raise ValueError(f"스키마에 없는 필드입니다: {', '.join(sorted(unknown))}")

    wrong_type = [
        name for name in (truth.get("booleans") or {}) if name not in _BOOLEAN_FIELDS
    ]
    if wrong_type:
        raise ValueError(
            f"booleans에 boolean이 아닌 필드가 있습니다: {', '.join(sorted(wrong_type))}"
        )


def load_truth(path: Path) -> dict:
    """정답표 JSON을 읽고 스키마와 맞는지 확인한다."""
    truth = json.loads(path.read_text(encoding="utf-8"))
    check_truth(truth)
    return truth


def score(truth: dict, runs: list[dict]) -> FixtureReport:
    """정답표와 N회 실행 결과(Product를 model_dump한 dict 목록)를 대조한다."""
    if not runs:
        raise ValueError("실행 결과가 없습니다.")
    check_truth(truth)

    report = FixtureReport(fixture=truth.get("fixture", "?"), runs=len(runs))

    for name, spec in (truth.get("booleans") or {}).items():
        values = [run.get(name) for run in runs]
        grades = [grade_boolean(spec["value"], v) for v in values]
        report.fields.append(_build(name, spec, values, grades))

    for name, spec in (truth.get("verbatim") or {}).items():
        values = [run.get(name) for run in runs]
        grades = [grade_verbatim(spec["value"], v) for v in values]
        report.fields.append(_build(name, spec, values, grades))

    for name, spec in (truth.get("keywords") or {}).items():
        values = [run.get(name) for run in runs]
        grades = [grade_keywords(spec.get("required"), spec.get("allowed"), v) for v in values]
        report.fields.append(_build(name, spec, values, grades))

    _score_attributes(truth, runs, report)
    _score_conflicts(truth, runs, report)
    _score_listing_text(truth, runs, report)

    graded_names = {f.name for f in report.fields}
    if report.listing_fields:
        graded_names.add("listing_text")
    report.ungraded = [
        name for name in runs[0] if name not in graded_names and name not in _NEVER_GRADED
    ]
    return report


def _build(name: str, spec: dict, values: list, grades: list[Grade]) -> FieldReport:
    return FieldReport(
        name=name,
        truth=spec.get("value", spec.get("allowed") or spec.get("required")),
        values=values,
        grades=grades,
        stability=classify_stability(grades, values),
        hard_flip=is_hard_flip(values),
        evidence=spec.get("evidence"),
    )


def _score_attributes(truth: dict, runs: list[dict], report: FixtureReport) -> None:
    """attributes는 항목 이름이 아니라 값으로 채점한다.

    같은 사실을 "용량"과 "배터리 용량"으로 번갈아 적는 것이 실측으로 확인됐다.
    이름 차이로 "놓쳤다"고 세면 사실 포착 여부가 아니라 라벨 표현을 재게 된다.
    이름이 흔들린 경우는 evidence에 남겨 따로 볼 수 있게 한다.
    """
    required = truth.get("attributes_required") or []
    forbidden = truth.get("attributes_forbidden") or []
    if not required and not forbidden:
        return

    per_run = [run.get("attributes", []) for run in runs]

    for item in required:
        wanted = item["value"]
        grades = [grade_attribute_value(wanted, attrs) for attrs in per_run]
        values = [g is Grade.OK for g in grades]
        names = sorted({n for attrs in per_run for n in attribute_names_for(wanted, attrs)})
        note = item.get("evidence")
        if len(names) > 1:
            note = f"항목 이름이 런마다 갈림: {names}"
        report.fields.append(
            FieldReport(
                name=f"attr값[{wanted}]",
                truth=True,
                values=values,
                grades=grades,
                stability=classify_stability(grades, values),
                hard_flip=False,
                evidence=note,
            )
        )

    for item in forbidden:
        wanted = item["value"]
        # 지어낸 값은 있으면 치명이다. 값 기준으로 보는 것은 required와 같다.
        grades = [
            Grade.C1 if grade_attribute_value(wanted, attrs) is Grade.OK else Grade.OK
            for attrs in per_run
        ]
        values = [g is Grade.OK for g in grades]
        report.fields.append(
            FieldReport(
                name=f"attr금지[{wanted}]",
                truth=False,
                values=values,
                grades=grades,
                stability=classify_stability(grades, values),
                hard_flip=False,
                evidence=item.get("reason"),
            )
        )


def _score_conflicts(truth: dict, runs: list[dict], report: FixtureReport) -> None:
    """정답표가 요구한 모순이 conflicts에 담겼는지 본다.

    놓치면 C1이다. 모순을 못 잡으면 관련 규제 축이 통째로 빠질 수 있다.
    """
    for item in truth.get("conflicts_required") or []:
        needle = item["must_contain"]
        values = [any(needle in c for c in run.get("conflicts", [])) for run in runs]
        grades = [Grade.OK if found else Grade.C1 for found in values]
        report.fields.append(
            FieldReport(
                name=f"conflicts[{needle}]",
                truth=True,
                values=values,
                grades=grades,
                stability=classify_stability(grades, values),
                hard_flip=is_hard_flip(values),
                evidence=item.get("evidence"),
            )
        )


def _score_listing_text(truth: dict, runs: list[dict], report: FixtureReport) -> None:
    """listing_text에 담겨야 할 판매자 문구와 섞이면 안 되는 문구를 따로 본다.

    놓치면 C1이다. 선택 프롬프트는 표시광고를 listing_text만 보고 정하므로, 의심 문구가
    빠지면 표시광고 심사가 통째로 빠진다(conflicts 누락이 C1인 이유와 같다).
    구매자 리뷰나 플랫폼 공통 문구가 섞이면 C3이다. 페이지에 있는 문구라 지어낸 것은
    아니고, 표시광고를 괜히 돌리게 만드는 쪽이다.
    """
    per_run = [run.get("listing_text") or [] for run in runs]

    for item in truth.get("listing_text_required") or []:
        needle = item["must_contain"]
        values = [any(needle in line for line in lines) for lines in per_run]
        grades = [Grade.OK if found else Grade.C1 for found in values]
        report.listing_fields.append(
            FieldReport(
                name=f"listing[{needle}]",
                truth=True,
                values=values,
                grades=grades,
                stability=classify_stability(grades, values),
                hard_flip=False,
                evidence=item.get("evidence"),
            )
        )

    for item in truth.get("listing_text_forbidden") or []:
        needle = item["must_not_contain"]
        values = [any(needle in line for line in lines) for lines in per_run]
        grades = [Grade.C3 if found else Grade.OK for found in values]
        report.listing_fields.append(
            FieldReport(
                name=f"listing금지[{needle}]",
                truth=False,
                values=values,
                grades=grades,
                stability=classify_stability(grades, values),
                hard_flip=False,
                evidence=item.get("evidence"),
            )
        )
