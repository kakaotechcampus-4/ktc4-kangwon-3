"""커밋된 정답표가 실제 스키마와 맞는지 검사한다. LLM을 부르지 않는다.

정답표 필드명에 오타가 있으면 그 필드는 모델 출력에서 항상 None으로 읽혀
"정답"으로 채점된다. 조용히 통과하면서 측정값만 오염시키므로 여기서 막는다.
"""

import json
from pathlib import Path

import pytest

from app.eval.scoring import check_truth, load_truth

TRUTH_DIR = Path(__file__).parent / "eval_truth"
TRUTH_FILES = sorted(TRUTH_DIR.glob("*.json"))


def test_정답표가_하나라도_있어야_한다():
    assert TRUTH_FILES, f"정답표가 없습니다: {TRUTH_DIR}"


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_커밋된_정답표는_스키마와_맞는다(path: Path):
    load_truth(path)


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_정답표에_사람_판단_근거가_남아_있다(path: Path):
    # null과 false를 가르는 판단이 가장 자주 틀리는 지점이라, 근거가 없으면
    # 나중에 정답 자체가 틀렸을 가능성을 걸러낼 수 없다.
    truth = json.loads(path.read_text(encoding="utf-8"))
    for name, spec in (truth.get("booleans") or {}).items():
        assert spec.get("evidence"), f"{path.stem}.{name}: evidence가 없습니다"
        assert spec.get("why_not_other"), f"{path.stem}.{name}: why_not_other가 없습니다"


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_정답표에_픽스처와_검토자가_적혀_있다(path: Path):
    truth = json.loads(path.read_text(encoding="utf-8"))
    assert truth.get("fixture"), "fixture 이름이 없습니다"
    assert truth.get("reviewed_by"), "누가 판단했는지 없습니다"
    assert truth.get("reviewed_at"), "언제 판단했는지 없습니다"


def test_스키마에_없는_필드명은_거부한다():
    with pytest.raises(ValueError, match="스키마에 없는 필드"):
        check_truth({"booleans": {"battery_incuded": {"value": None}}})


def test_boolean이_아닌_필드를_booleans에_두면_거부한다():
    # target_age는 문자열 필드라 3-state 채점표로 볼 수 없다.
    with pytest.raises(ValueError, match="boolean이 아닌 필드"):
        check_truth({"booleans": {"target_age": {"value": None}}})
