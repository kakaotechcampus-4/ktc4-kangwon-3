"""RegulatoryTool.execute: 선택 확인·SKIPPED는 공통 처리하고, 선택된 경우만 _run을 부름."""

import json

import pytest

from app.observability.trace import trace_note, trace_run
from app.schemas.agent import ToolSelectionItem
from app.schemas.product import Product
from app.schemas.schemas import Determination, RegulatoryFinding, RiskLevel, ToolName, ToolResult, ToolStatus
from app.tools.base import RegulatoryTool

PRODUCT = Product(product_id="p-1")


class _Tool(RegulatoryTool):
    tool_name = ToolName.RADIO

    def __init__(self):
        self.calls: list[Product] = []

    def _run(self, product, decision):
        self.calls.append(product)
        return ToolResult(tool_name=self.tool_name, selected=True, selection_reason=decision.reason,
                          status=ToolStatus.SUCCESS)


def _decision(selected=True, tool_name=ToolName.RADIO):
    return ToolSelectionItem(tool_name=tool_name, selected=selected, reason="무선 기능")


def test_선택되면_run을_부른다():
    tool = _Tool()

    result = tool.execute(PRODUCT, _decision())

    assert tool.calls == [PRODUCT]
    assert result.status is ToolStatus.SUCCESS


def test_미선택이면_run_없이_SKIPPED와_선택_이유를_돌려준다():
    tool = _Tool()

    result = tool.execute(PRODUCT, _decision(selected=False))

    assert tool.calls == []
    assert (result.status, result.selected, result.selection_reason) == (ToolStatus.SKIPPED, False, "무선 기능")


def test_다른_Tool의_선택_결정이면_ValueError():
    with pytest.raises(ValueError, match="이름"):
        _Tool().execute(PRODUCT, _decision(tool_name=ToolName.CUSTOMS))


def test_기록_중이면_Tool_실행을_단계로_남기고_결과를_요약한다(tmp_path):
    with trace_run(tmp_path) as recorder:
        _Tool().execute(PRODUCT, _decision())
        _Tool().execute(PRODUCT, _decision(selected=False))

    assert recorder.steps == [
        {"id": "s1", "kind": "tool", "tool": "radio_compliance", "selected": True, "reason": "무선 기능",
         "result": {"status": "success", "findings": [], "missing_information": [], "required_actions": []}},
        {"id": "s2", "kind": "tool", "tool": "radio_compliance", "selected": False, "reason": "무선 기능",
         "result": {"status": "skipped", "findings": [], "missing_information": [], "required_actions": []}},
    ]


def test_판단_ID는_실행_안_번호로_바꾸고_파일_안_다른_곳의_같은_ID도_같이_바꾼다(tmp_path):
    finding = RegulatoryFinding(tool_name=ToolName.RADIO, subject="전파 인증", determination=Determination.REQUIRED,
                                risk_level=RiskLevel.HIGH, summary="요약", rationale="근거")

    class _Finding(_Tool):
        def _run(self, product, decision):
            return super()._run(product, decision).model_copy(update={"findings": [finding]})

    with trace_run(tmp_path) as recorder:
        _Finding().execute(PRODUCT, _decision())
        trace_note("checked", [finding.finding_id])
        trace_note("prompt", f'{{"finding_id": "{finding.finding_id}"}}')

    saved = json.loads((tmp_path / "run-1.json").read_text(encoding="utf-8"))
    assert saved["steps"][0]["result"]["findings"] == [
        {"id": "f1", "subject": "전파 인증", "determination": "required", "risk_level": "high"},
    ]
    assert (saved["info"]["checked"], saved["info"]["prompt"]) == (["f1"], '{"finding_id": "f1"}')
    assert finding.finding_id not in json.dumps(saved, ensure_ascii=False)
    # 메모리의 기록은 원래 값 그대로 (저장할 때만 바꿈)
    assert recorder.info["checked"] == [finding.finding_id]


def test_Tool이_실패하면_단계에_예외_이름과_메시지를_남기고_예외는_그대로_던진다(tmp_path):
    class _Broken(_Tool):
        def _run(self, product, decision):
            raise RuntimeError("조회 실패")

    with trace_run(tmp_path) as recorder:
        with pytest.raises(RuntimeError):
            _Broken().execute(PRODUCT, _decision())

    assert recorder.steps[0]["error"] == {"type": "RuntimeError", "message": "조회 실패"}
    assert "result" not in recorder.steps[0]
