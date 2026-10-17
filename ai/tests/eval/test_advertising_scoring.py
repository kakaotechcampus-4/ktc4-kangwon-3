"""표시·광고 평가셋 채점 규칙."""

import json

import pytest

from app.eval.advertising_scoring import InputsMismatch, inputs_digest, load_eval_set, overlaps, score_case

CASE = {
    "must_flag": [{"text": "통기성 2배", "risk_type": "performance_quality"},
                  {"text": "허리 통증 완화", "risk_type": "body_effect"}],
    "must_not_flag": [{"text": "색상: 카키"}],
    "acceptable": [{"text": "튼튼한 프레임"}],
}


def _phrase(text: str, risk_type: str = "performance_quality") -> dict:
    return {"text": text, "risk_type": risk_type}


def test_정답을_포함하거나_정답_안에_포함된_탐지는_같은_문구로_본다():
    assert overlaps("메쉬 통기성 2배 등받이", "통기성 2배")
    assert overlaps("통기성", "통기성 2배")
    assert overlaps("UV 차단", "uv  차단")
    assert not overlaps("통기성 3배", "통기성 2배")
    assert not overlaps("", "통기성 2배")


def test_맞힘_놓침_오탐_미분류를_나눠_센다():
    score = score_case(CASE, [_phrase("통기성 2배"), _phrase("색상: 카키"), _phrase("가벼운 무게")])

    assert score.hits == ["통기성 2배"]
    assert score.misses == ["허리 통증 완화"]
    assert score.false_positives == ["색상: 카키"]
    assert score.unlabeled == ["가벼운 무게"]


def test_판단_보류_문구는_어느_쪽으로도_세지_않는다():
    score = score_case(CASE, [_phrase("튼튼한 프레임")])

    assert score.false_positives == [] and score.unlabeled == []


def test_잡았지만_유형이_다르면_따로_센다():
    score = score_case(CASE, [_phrase("허리 통증 완화", "performance_quality")])

    assert score.hits == ["허리 통증 완화"]
    assert score.type_mismatches == ["허리 통증 완화"]


def test_입력_파일_지문이_다르면_불러오지_않는다(tmp_path):
    inputs = tmp_path / "inputs.json"
    inputs.write_text(json.dumps({"p": ["통기성 2배"]}, ensure_ascii=False), encoding="utf-8")
    truth = tmp_path / "dev.json"
    truth.write_text(json.dumps({"inputs_file": "inputs.json", "inputs_sha256_12": inputs_digest(inputs.read_text(encoding="utf-8")),
                                 "cases": []}), encoding="utf-8")

    _, loaded = load_eval_set(truth, tmp_path)
    assert loaded == {"p": ["통기성 2배"]}

    inputs.write_text(json.dumps({"p": ["통기성 3배"]}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(InputsMismatch):
        load_eval_set(truth, tmp_path)


def test_줄바꿈만_다르면_지문이_같다():
    assert inputs_digest("가\r\n나\n") == inputs_digest("가\n나\n")
