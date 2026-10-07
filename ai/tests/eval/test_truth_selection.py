"""선택 정답표가 실제 툴 목록과 맞는지 검사한다. LLM을 부르지 않는다.

툴 이름에 오타가 있으면 그 툴은 채점에서 조용히 빠진다. 측정값만 오염되므로
여기서 막는다. 추출 정답표(test_eval_truth_files.py)와 같은 이유다.
"""

import json
from pathlib import Path

import pytest

from app.agents.selection import _PROMPT_PATH as SELECTION_PROMPT_PATH
from app.eval.runner import prompt_fingerprint
from app.schemas.schemas import ToolName

TRUTH_DIR = Path(__file__).parents[1] / "eval_truth_selection"
TRUTH_FILES = sorted(TRUTH_DIR.glob("*.json"))


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    # json.loads는 같은 키가 두 번 나오면 뒤의 값으로 조용히 덮어쓴다. 손으로 고치다
    # 툴 항목을 복사해 붙이면 앞의 판단이 흔적 없이 사라지므로 여기서 막는다.
    keys = [key for key, _ in pairs]
    duplicated = sorted({key for key in keys if keys.count(key) > 1})
    if duplicated:
        raise ValueError(f"같은 키가 두 번 있습니다: {duplicated}")
    return dict(pairs)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)


def test_선택_정답표가_하나라도_있어야_한다():
    assert TRUTH_FILES, f"정답표가 없습니다: {TRUTH_DIR}"


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_여섯_개_툴이_각각_한_번씩_있다(path: Path):
    # 선택 에이전트는 미선택 툴도 이유와 함께 보고한다. 정답표도 같은 규격이어야
    # "빠뜨린 것"과 "미선택으로 판단한 것"을 구분할 수 있다.
    tools = _load(path)["tools"]

    assert set(tools) == {name.value for name in ToolName}


def test_같은_툴이_두_번_적히면_읽을_때_실패한다(tmp_path: Path):
    duplicated = tmp_path / "duplicated.json"
    duplicated.write_text(
        '{"tools": {"radio_compliance": {"selected": true}, "radio_compliance": {"selected": false}}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="radio_compliance"):
        _load(duplicated)


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_선택_여부가_참거짓으로만_적혀_있다(path: Path):
    # 추출과 달리 선택은 유보가 없다. 실행하거나 안 하거나 둘 중 하나다.
    tools = _load(path)["tools"]

    for name, spec in tools.items():
        assert isinstance(spec.get("selected"), bool), f"{path.stem}.{name}: selected가 참거짓이 아닙니다"


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_선택_정답표에_사람_판단_근거가_남아_있다(path: Path):
    tools = _load(path)["tools"]

    for name, spec in tools.items():
        assert spec.get("evidence"), f"{path.stem}.{name}: evidence가 없습니다"
        assert spec.get("why_not_other"), f"{path.stem}.{name}: why_not_other가 없습니다"


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_선택_정답표에_픽스처와_검토자가_적혀_있다(path: Path):
    truth = _load(path)

    assert truth.get("fixture"), "fixture 이름이 없습니다"
    assert truth.get("reviewed_by"), "누가 판단했는지 없습니다"
    assert truth.get("reviewed_at"), "언제 판단했는지 없습니다"


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_정답을_매긴_선택_프롬프트가_지금과_같다(path: Path):
    # 추출 정답은 페이지 사실이라 프롬프트와 무관하지만, 선택 정답은 선택 프롬프트의
    # 규칙에서 나온다. 프롬프트가 바뀌면 정답표가 옛 규칙 기준으로 조용히 남으므로,
    # 바뀐 규칙으로 정답을 다시 검토하게 만든다.
    recorded = _load(path).get("prompt_sha256")
    current = prompt_fingerprint(SELECTION_PROMPT_PATH)

    assert recorded, f"{path.stem}: 어떤 선택 프롬프트로 정답을 매겼는지(prompt_sha256)가 없습니다"
    assert recorded == current, (
        f"{path.stem}: 선택 프롬프트가 정답을 매긴 뒤 바뀌었습니다. 바뀐 규칙으로 정답을 다시 "
        f"검토한 뒤 prompt_sha256을 {current}로 갱신하세요."
    )


@pytest.mark.parametrize("path", TRUTH_FILES, ids=lambda p: p.stem)
def test_추출_정답표와_같은_픽스처를_가리킨다(path: Path):
    # 두 정답표가 다른 페이지를 가리키면 "추출 오류가 선택에 미치는 영향"을
    # 잴 수 없다. 같은 픽스처여야 두 측정을 나란히 놓을 수 있다.
    extraction_truth = Path(__file__).parents[1] / "eval_truth" / path.name

    assert extraction_truth.exists(), f"짝이 되는 추출 정답표가 없습니다: {extraction_truth}"
    assert _load(path)["fixture"] == _load(extraction_truth)["fixture"]
