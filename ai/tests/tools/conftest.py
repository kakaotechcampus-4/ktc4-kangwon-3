"""규제 Tool 리팩토링 기준선. Tool 5개의 execute 결과를 테스트별로 저장해 두고 같은지 비교.

기존 Tool 테스트가 만든 결과(가짜 모델 + 법령 픽스처)를 그대로 기준선으로 씀.
기준선 다시 만들기: ``UPDATE_TOOL_BASELINE=1 pytest tests/tools``
"""

import json
import os
from functools import cache
from pathlib import Path

import pytest

from app.tools.children import ChildrenTool
from app.tools.customs import CustomsTool
from app.tools.electrical import ElectricalTool
from app.tools.food_drug import FoodDrugTool
from app.tools.radio import RadioTool

BASELINE_DIR = Path(__file__).parent / "baseline"
_TOOLS = (ChildrenTool, CustomsTool, ElectricalTool, FoodDrugTool, RadioTool)
_UPDATE = os.environ.get("UPDATE_TOOL_BASELINE") == "1"
# 실행마다 달라지는 자동 생성 필드 (실행 시각, 판단 UUID)
_VOLATILE = {"executed_at": True, "findings": {"__all__": {"finding_id"}}}
# 갱신 모드에서 세션 끝에 쓸 결과 (Tool 이름 → 테스트 ID → 결과 목록)
_recorded: dict[str, dict[str, list[dict]]] = {}


def _path(tool_name: str) -> Path:
    return BASELINE_DIR / f"{tool_name}.json"


@cache
def _load(tool_name: str) -> dict[str, list[dict]]:
    """Tool 하나의 기준선을 읽는다.

    Args:
        tool_name: ToolName 값.

    Returns:
        dict[str, list[dict]]: 테스트 ID별 execute 결과 목록. 파일이 없으면 빈 dict.
    """
    path = _path(tool_name)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _recording(execute, results: list[tuple[str, dict]]):
    """execute를 감싸 결과를 JSON 모양으로 모은다."""
    def wrapper(self, product, decision):
        result = execute(self, product, decision)
        results.append((self.tool_name.value, result.model_dump(mode="json", exclude=_VOLATILE)))
        return result
    return wrapper


@pytest.fixture(autouse=True)
def tool_baseline(request, monkeypatch):
    """테스트 하나에서 나온 Tool 결과를 기준선과 비교한다. 갱신 모드면 모으기만 함."""
    results: list[tuple[str, dict]] = []
    for tool in _TOOLS:
        monkeypatch.setattr(tool, "execute", _recording(tool.execute, results))
    yield
    by_tool: dict[str, list[dict]] = {}
    for tool_name, dumped in results:
        by_tool.setdefault(tool_name, []).append(dumped)
    node = request.node.nodeid
    for tool_name, dumped in by_tool.items():
        if _UPDATE:
            _recorded.setdefault(tool_name, {})[node] = dumped
            continue
        expected = _load(tool_name).get(node)
        assert expected is not None, f"기준선에 없는 테스트: {node} (UPDATE_TOOL_BASELINE=1로 생성)"
        assert dumped == expected


def pytest_sessionfinish(session):
    """갱신 모드면 모은 결과를 기존 기준선에 덮어 쓴다 (이번에 안 돈 테스트는 유지)."""
    if not _UPDATE:
        return
    BASELINE_DIR.mkdir(exist_ok=True)
    for tool_name, entries in _recorded.items():
        merged = {**_load(tool_name), **entries}
        _path(tool_name).write_text(
            json.dumps(merged, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
