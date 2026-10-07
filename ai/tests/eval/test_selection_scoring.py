"""선택 채점과 "추출 탓 / 선택 탓" 나누기를 LLM 없이 검증한다(SELECTION_EVAL.md 1·2절)."""

import json
from pathlib import Path

import pytest

from app.eval.grading import Grade, Stability
from app.eval.selection_scoring import (
    Blame,
    blame_for,
    correct_booleans,
    grade_selection,
    load_selection_truth,
    only_in_b,
    score_mode,
)
from app.schemas.schemas import ToolName

TRUTH_DIR = Path(__file__).parents[1] / "eval_truth_selection"


def _response(**selected: bool) -> dict:
    """툴 이름(값) → 선택 여부. 적지 않은 툴은 미선택."""
    return {
        "decisions": [
            {"tool_name": tool.value, "selected": selected.get(tool.value, False), "reason": "테스트"}
            for tool in ToolName
        ]
    }


def _selection_truth(**selected: bool) -> dict:
    return {
        "tools": {
            tool.value: {"selected": selected.get(tool.value, False), "evidence": "e", "why_not_other": "w"}
            for tool in ToolName
        }
    }


@pytest.mark.parametrize(
    ("truth", "predicted", "expected"),
    [(True, True, Grade.OK), (True, False, Grade.C1), (False, True, Grade.C3), (False, False, Grade.OK)],
)
def test_선택은_해야_하는데_안_하면_C1_안_해도_되는데_하면_C3(truth, predicted, expected):
    assert grade_selection(truth, predicted) is expected


def test_모드_A_입력은_boolean만_정답으로_바꾸고_null_정답도_null로_넣는다():
    product = {"product_name": "보조배터리", "category": "휴대폰 액세서리",
               "wireless_charging": False, "electrical_powered": True}
    truth = {"booleans": {"wireless_charging": {"value": None}, "electrical_powered": {"value": True}}}

    corrected = correct_booleans(product, truth)

    assert corrected["wireless_charging"] is None
    assert corrected["electrical_powered"] is True
    assert corrected["product_name"] == "보조배터리"
    assert corrected["category"] == "휴대폰 액세서리"
    assert product["wireless_charging"] is False  # 원본은 그대로


@pytest.mark.parametrize(
    ("truth_value", "extracted", "expected"),
    [
        (True, False, Blame.EXTRACTION),   # 있는 것을 없다고 확정
        (None, False, Blame.EXTRACTION),   # 근거 없이 없다고 확정
        (True, None, Blame.SELECTION),     # 추출은 모른다고 넘겼는데 선택이 없음으로 봄(원칙 2)
        (True, True, Blame.NOISE),         # 입력이 A와 같은데 선택만 흔들림
    ],
)
def test_B에서만_놓친_툴은_판단_필드의_추출값으로_탓을_나눈다(truth_value, extracted, expected):
    truth = {"booleans": {"wireless_charging": {"value": truth_value}}}

    assert blame_for(ToolName.RADIO, truth, {"wireless_charging": extracted}) == expected


def test_정답의_모순을_추출이_빠뜨려_전기를_놓치면_추출_탓이다():
    # power_bank: 판단 필드가 전부 null이라 모순이 전기 선택의 유일한 근거다(원칙 6).
    truth = {"booleans": {}, "conflicts_required": [{"must_contain": "1460mAh"}]}

    assert blame_for(ToolName.ELECTRICAL, truth, {"conflicts": []}) == Blame.EXTRACTION
    assert blame_for(ToolName.ELECTRICAL, truth, {"conflicts": ["1460mAh와 배터리 미포함이 충돌"]}) == Blame.NOISE



def test_판단_필드는_같고_다른_boolean이_틀렸으면_추출의_간접_영향으로_센다():
    # power_bank 실측: 무선 필드는 A·B 모두 null인데, 추출이 다른 필드를 근거 없이 확정한
    # B에서만 전파를 놓쳤다. A·B 입력은 boolean만 다르므로 차이는 그 필드들에서 온다.
    truth = {"booleans": {"wireless_charging": {"value": None}, "electrical_powered": {"value": None}}}

    assert blame_for(ToolName.RADIO, truth, {"wireless_charging": None, "electrical_powered": True}) == Blame.EXTRACTION_OTHER
    assert blame_for(ToolName.RADIO, truth, {"wireless_charging": None, "electrical_powered": None}) == Blame.NOISE


def test_판단_필드가_없는_표시광고도_boolean이_달랐는지로_나눈다():
    truth = {"booleans": {"medical_claim": {"value": True}}}

    assert blame_for(ToolName.LABEL_AD, truth, {"medical_claim": None}) == Blame.EXTRACTION_OTHER
    assert blame_for(ToolName.LABEL_AD, truth, {"medical_claim": True}) == Blame.NOISE

def test_툴별로_결정을_세고_값이_갈리면_불안정이다():
    truth = _selection_truth(radio_compliance=True, customs_requirements=True)
    responses = [
        _response(customs_requirements=True, radio_compliance=True),
        _response(customs_requirements=True, radio_compliance=False),
        _response(customs_requirements=True, labeling_advertising_detection=True),
    ]

    report = score_mode("x", "B", truth, responses)
    counts = report.counts()

    assert counts["decisions"] == 18
    assert counts["c1_decisions"] == 2      # 전파를 2번 놓침
    assert counts["c3_decisions"] == 1      # 표시광고를 1번 괜히 선택
    radio = next(t for t in report.tools if t.tool is ToolName.RADIO)
    assert radio.stability is Stability.UNSTABLE
    assert radio.worst is Grade.C1


def test_B에서만_놓친_결정만_골라내고_실패한_회차는_짝에서_뺀다():
    selection_truth = _selection_truth(radio_compliance=True)
    extraction_truth = {"booleans": {"wireless_charging": {"value": None}}}
    products = [{"wireless_charging": False}, {"wireless_charging": None}, {"wireless_charging": False}]
    mode_a = [_response(radio_compliance=True), _response(radio_compliance=False), None]
    mode_b = [_response(radio_compliance=False), _response(radio_compliance=False), _response()]

    found = only_in_b("power_bank", selection_truth, extraction_truth, products, mode_a, mode_b)

    # 0회차: A는 선택, B는 놓침 → 추출의 근거 없는 false 탓
    # 1회차: A도 놓쳤으므로 선택 에이전트 자체 오류라 여기서 세지 않는다
    # 2회차: A가 실패해 짝이 없다
    assert [(d.run, d.tool, d.blame) for d in found] == [(0, ToolName.RADIO, Blame.EXTRACTION)]
    assert found[0].fields == {
        "wireless_comm": (None, None),
        "wireless_charging": (None, False),
        "wireless_shield": (None, None),
    }


def test_같은_툴이_두_번_적힌_정답표는_읽을_때_실패한다(tmp_path):
    path = tmp_path / "dup.json"
    path.write_text('{"tools": {"radio_compliance": {"selected": true}, "radio_compliance": {"selected": false}}}',
                    encoding="utf-8")

    with pytest.raises(ValueError, match="radio_compliance"):
        load_selection_truth(path)


def test_툴이_빠지거나_선택이_참거짓이_아닌_정답표는_읽을_때_실패한다(tmp_path):
    missing = tmp_path / "missing.json"
    missing.write_text(json.dumps({"tools": {"radio_compliance": {"selected": True}}}), encoding="utf-8")
    not_bool = tmp_path / "not_bool.json"
    truth = _selection_truth()
    truth["tools"]["radio_compliance"]["selected"] = "true"
    not_bool.write_text(json.dumps(truth), encoding="utf-8")

    with pytest.raises(ValueError, match="6개 툴"):
        load_selection_truth(missing)
    with pytest.raises(ValueError, match="참거짓"):
        load_selection_truth(not_bool)


@pytest.mark.parametrize("path", sorted(TRUTH_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_실제_선택_정답표를_러너가_읽을_수_있다(path):
    assert load_selection_truth(path)["tools"]
