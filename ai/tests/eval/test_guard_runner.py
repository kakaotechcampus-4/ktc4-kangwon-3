"""입력 가드 평가: 회차 기록, 기대 판정별 집계, 평가셋 형식. 모델 호출 없음."""

import json

import pytest

from app.agents.input_guard import GuardOutcome, GuardVerdict
from app.eval import guard_runner


class _Guard:
    """정해 둔 판정을 차례로 돌려주는 가짜 가드. 예외를 넣으면 그 회차에 올림."""

    def __init__(self, *results) -> None:
        self.results = list(results)
        self.inputs = []

    def run(self, guard_input):
        self.inputs.append(guard_input)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _out(outcome: str, **extra) -> dict:
    return {"outcome": outcome, **extra}


def test_회차마다_판정과_점수를_남기고_가드_예외는_error로_남긴다():
    guard = _Guard(
        GuardVerdict(outcome=GuardOutcome.SUSPECT, text_score=0.4, image_scores=[0.1, 0.7]),
        RuntimeError("판단 실패"),
    )

    outputs = guard_runner.run_case(guard, "c1", {"texts": ["글"], "image_urls": ["data:image/jpeg;base64,AA"]}, 2)

    assert outputs[0]["outcome"] == "suspect"
    assert outputs[0]["text_score"] == 0.4
    assert outputs[0]["image_score"] == 0.7
    assert outputs[0]["has_images"] is True
    assert outputs[1] == {"outcome": "error", "error": "RuntimeError: 판단 실패"}
    assert guard.inputs[0].product_id == "c1"
    assert guard.inputs[0].texts == ["글"]


def test_판단_실패·못_본_이미지·오류가_있던_회차는_집계에서_뺀다():
    assert guard_runner.counted_outcome(_out("suspect", failed_calls=1)) == guard_runner.INCOMPLETE
    assert guard_runner.counted_outcome(_out("suspect", skipped_images=1)) == guard_runner.INCOMPLETE
    assert guard_runner.counted_outcome(_out("error")) == guard_runner.INCOMPLETE
    assert guard_runner.counted_outcome(_out("suspect", failed_calls=0)) == "suspect"


def test_기대_판정별로_틀린_사례를_센다():
    cases = [
        {"id": "b1", "group": "공격 글", "expect": "block"},
        {"id": "b2", "group": "공격 글", "expect": "block"},
        {"id": "d1", "group": "공격 글", "expect": "detect"},
        {"id": "d2", "group": "공격 글", "expect": "detect"},
        {"id": "n1", "group": "오인 문구", "expect": "pass"},
        {"id": "n2", "group": "오인 문구", "expect": "pass"},
        {"id": "skipped", "group": "공격 글", "expect": "block"},
    ]
    results = {
        "b1": [_out("block"), _out("suspect")],
        "b2": [_out("block"), _out("pass")],
        "d1": [_out("suspect"), _out("suspect")],
        "d2": [_out("pass"), _out("block")],
        "n1": [_out("pass"), _out("suspect")],
        "n2": [_out("pass"), _out("block", failed_calls=1), _out("block")],
    }

    reports = guard_runner.score(cases, results)

    assert reports["block"].cases == 2
    assert reports["block"].outcomes == {"block": 2, "suspect": 1, "pass": 1}
    assert reports["block"].wrong_cases == ["b2"]
    assert reports["detect"].wrong_cases == ["d2"]
    assert reports["pass"].wrong_cases == ["n2"]
    assert reports["pass"].outcomes[guard_runner.INCOMPLETE] == 1
    assert reports["pass"].counted == 4


def test_요약에_기대_판정별_비율과_걸린_시간을_출력한다(capsys):
    cases = [
        {"id": "b1", "group": "공격 글", "expect": "block"},
        {"id": "d1", "group": "공격 글", "expect": "detect"},
        {"id": "n1", "group": "정상 원문", "expect": "pass"},
    ]
    results = {
        "b1": [_out("block", text_score=0.97, elapsed_ms=1000), _out("suspect", text_score=0.5, elapsed_ms=3000)],
        "d1": [_out("suspect", text_score=0.6, elapsed_ms=2000)],
        "n1": [_out("pass", text_score=0.01, elapsed_ms=1000),
               _out("suspect", failed_calls=2, has_images=True, elapsed_ms=5000)],
    }

    guard_runner.print_report(cases, results)

    printed = capsys.readouterr().out
    assert "점수 0.50~0.97" in printed
    assert "직접 지시 공격 1건 차단: 1/2 (50%)" in printed
    assert "직접 지시 공격 1건 탐지 (차단+의심): 2/2 (100%)" in printed
    assert "결과 미리 쓰기 공격 1건 탐지 (차단+의심): 1/1 (100%)" in printed
    assert "정상 1건 오차단: 0/1 (0%)" in printed
    assert "제외한 회차 (판단 호출 실패·못 본 이미지·오류): 1" in printed
    assert "글만: 중앙값 1.5초 / 최대 3.0초 (4회)" in printed
    assert "이미지 포함: 중앙값 5.0초 / 최대 5.0초 (1회)" in printed


@pytest.mark.parametrize("name", guard_runner.SETS)
def test_평가셋_사례는_ID가_겹치지_않고_기대_판정과_묶음이_정해져_있다(name):
    truth = json.loads((guard_runner.TRUTH_DIR / f"{name}.json").read_text(encoding="utf-8"))

    ids = [case["id"] for case in truth["cases"]]
    assert len(ids) == len(set(ids))
    assert {case["expect"] for case in truth["cases"]} <= set(guard_runner.CORRECT)
    assert {case["group"] for case in truth["cases"]} <= set(truth["groups"])
    assert truth["inputs_file"].startswith("tests/fixtures/_raw/")
