"""시나리오 평가 정답표(개발 50, 홀드아웃 15)가 러너가 읽을 수 있는 형식인지 검사한다. LLM을 부르지 않는다.

형식이 깨진 정답은 측정을 시작하기 전에 러너가 멈추지만, 원문이 있는 PC에서만 드러난다. 여기서 먼저 막는다.
"""

import re
from pathlib import Path

import pytest

from app.eval.selection_scoring import load_selection_truth

TRUTH_DIR = Path(__file__).parents[1] / "eval_truth_scenario"
# 표본별 상품 수. 정답을 더하거나 빼면 docs/current/eval/SCENARIO_EVAL.md의 숫자도 다시 재야 하므로 여기서 묶어 둔다.
EXPECTED_COUNTS = {"dev": 50, "holdout": 15}
TRUTH_FILES = sorted(TRUTH_DIR.glob("*/*.json"))


def test_표본별_정답_수가_문서와_같다():
    counts = {name: len(list((TRUTH_DIR / name).glob("*.json"))) for name in EXPECTED_COUNTS}

    assert counts == EXPECTED_COUNTS


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_정답은_6개_Tool_참거짓과_자기_원문_경로를_가진다(path: Path):
    truth = load_selection_truth(path)

    assert truth["fixture"] == f"{path.stem}/text.txt"
    assert re.fullmatch(r"(strat|holdout)_\d{2}", path.stem)


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_정답은_사람이_확정했고_근거를_적었다(path: Path):
    truth = load_selection_truth(path)

    assert truth["reviewed_by"]
    assert all(spec.get("evidence") for spec in truth["tools"].values())

