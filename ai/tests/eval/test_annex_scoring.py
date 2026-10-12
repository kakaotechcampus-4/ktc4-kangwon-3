"""별표 파싱 정답셋과 채점을 모델 없이 확인한다."""

from pathlib import Path

import pytest

from app.eval.annex_scoring import ANNEX_TRUTH_DIR, load_annex_truth, score_annex
from app.schemas.agents.annex import AnnexSkippedRow
from app.utils.annex_check import check_annex

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "annex"
_TRUTHS = sorted(ANNEX_TRUTH_DIR.glob("*.json"))
_NOTICE_6 = ANNEX_TRUTH_DIR / "전기용품및생활용품안전관리운용요령_별표0006-00.json"


@pytest.mark.parametrize("path", _TRUTHS, ids=lambda path: path.stem)
def test_정답셋은_원문_대조를_통과한다(path):
    fixture, truth = load_annex_truth(path)

    assert fixture == path.stem
    assert check_annex((_FIXTURES / fixture / "content.txt").read_text(encoding="utf-8"), truth) == []


def test_정답과_같은_출력은_모든_행이_맞는다():
    _, truth = load_annex_truth(_NOTICE_6)

    score = score_annex(truth, truth)

    assert (score.expected_rows, score.matched_rows) == (20, 20)
    assert (score.missing, score.extra, score.category_errors, score.field_errors) == ([], [], [], [])
    assert score.scheme_ok and score.skipped_ok and score.notes_ok


def test_공백과_테두리_차이는_같은_글자로_본다():
    _, truth = load_annex_truth(_NOTICE_6)
    spaced = truth.model_copy(update={"items": [
        item.model_copy(update={"item_name": item.item_name.replace(" ", "  ")}) for item in truth.items
    ]})

    assert score_annex(truth, spaced).matched_rows == 20


def test_빠진_행_남는_행_분류_오류_문구_오류를_나눠_센다():
    _, truth = load_annex_truth(_NOTICE_6)
    items = list(truth.items)
    # 가구 행: 분류 괄호 문구를 분류에 남기고 한정 문구를 빠뜨린 경우
    items[2] = items[2].model_copy(update={
        "category_path": ["2. 생활", "가. 가구(높이 762mm 이상의 가정용 서랍장 및 사무용 파일링 캐비넷에 한정한다)"],
        "conditions": [],
    })
    extra = items[0].model_copy(update={"item_label": "③", "item_name": "없는 품목"})
    actual = truth.model_copy(update={
        "items": [*items[:-1], extra],
        "skipped": [AnnexSkippedRow(item_label="라.", reason="삭제")],
        "notes": ["없는 비고"],
    })

    score = score_annex(truth, actual)

    assert score.matched_rows == 19
    assert score.missing == ["5. 건축 > 물탱크 > ① 물탱크"]
    assert score.extra == ["1. 화학 > 폴리염화비닐관 > ③ 없는 품목"]
    assert len(score.category_errors) == 1 and score.category_errors[0].startswith("2. 생활 > 가. 가구 > ①")
    assert score.field_errors == ["2. 생활 > 가. 가구 > ① 높이 762mm 이상의 가정용 서랍장 및 사무용 파일링 캐비넷"]
    assert not score.skipped_ok
    assert not score.notes_ok
