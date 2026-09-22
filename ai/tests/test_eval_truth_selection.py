"""선택 정답표가 실제 툴 목록과 맞는지 검사한다. LLM을 부르지 않는다.

툴 이름에 오타가 있으면 그 툴은 채점에서 조용히 빠진다. 측정값만 오염되므로
여기서 막는다. 추출 정답표(test_eval_truth_files.py)와 같은 이유다.
"""

import json
from pathlib import Path

import pytest

from app.schemas.schemas import ToolName

TRUTH_DIR = Path(__file__).parent / "eval_truth_selection"
TRUTH_FILES = sorted(TRUTH_DIR.glob("*.json"))


def test_선택_정답표가_하나라도_있어야_한다():
    assert TRUTH_FILES, f"정답표가 없습니다: {TRUTH_DIR}"


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_여섯_개_툴이_각각_한_번씩_있다(path: Path):
    # 선택 에이전트는 미선택 툴도 이유와 함께 보고한다. 정답표도 같은 규격이어야
    # "빠뜨린 것"과 "미선택으로 판단한 것"을 구분할 수 있다.
    tools = json.loads(path.read_text(encoding="utf-8"))["tools"]

    assert set(tools) == {name.value for name in ToolName}


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_선택_여부가_참거짓으로만_적혀_있다(path: Path):
    # 추출과 달리 선택은 유보가 없다. 실행하거나 안 하거나 둘 중 하나다.
    tools = json.loads(path.read_text(encoding="utf-8"))["tools"]

    for name, spec in tools.items():
        assert isinstance(spec.get("selected"), bool), f"{path.stem}.{name}: selected가 참거짓이 아닙니다"


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_선택_정답표에_사람_판단_근거가_남아_있다(path: Path):
    tools = json.loads(path.read_text(encoding="utf-8"))["tools"]

    for name, spec in tools.items():
        assert spec.get("evidence"), f"{path.stem}.{name}: evidence가 없습니다"
        assert spec.get("why_not_other"), f"{path.stem}.{name}: why_not_other가 없습니다"


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_선택_정답표에_픽스처와_검토자가_적혀_있다(path: Path):
    truth = json.loads(path.read_text(encoding="utf-8"))

    assert truth.get("fixture"), "fixture 이름이 없습니다"
    assert truth.get("reviewed_by"), "누가 판단했는지 없습니다"
    assert truth.get("reviewed_at"), "언제 판단했는지 없습니다"


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_추출_정답표와_같은_픽스처를_가리킨다(path: Path):
    # 두 정답표가 다른 페이지를 가리키면 "추출 오류가 선택에 미치는 영향"을
    # 잴 수 없다. 같은 픽스처여야 두 측정을 나란히 놓을 수 있다.
    extraction_truth = Path(__file__).parent / "eval_truth" / path.name

    assert extraction_truth.exists(), f"짝이 되는 추출 정답표가 없습니다: {extraction_truth}"
    assert (
        json.loads(path.read_text(encoding="utf-8"))["fixture"]
        == json.loads(extraction_truth.read_text(encoding="utf-8"))["fixture"]
    )
