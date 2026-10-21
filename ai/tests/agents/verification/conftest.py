"""검증 에이전트 테스트 공용 설정.

- samples: 규칙 검사를 통과하는 최소 초안과 모델 검토 응답을 만드는 도우미
"""

from types import SimpleNamespace

import pytest

from app.agents.verification.schemas import _Issue, _Question, _Review
from app.schemas.product import Product
from app.schemas.schemas import (
    Determination,
    DraftAssessment,
    ElectricalAssessment,
    LegalSource,
    OverallStatus,
    RegulatoryFinding,
    RiskLevel,
    ToolName,
    ToolResult,
    ToolStatus,
)


def _finding() -> RegulatoryFinding:
    # possibly_required는 확정적 판단이 아니므로 실자료 근거 규칙의 대상이 아니다.
    return RegulatoryFinding(
        finding_id="f1",
        tool_name=ToolName.ELECTRICAL,
        subject="전지 내장 기기",
        determination=Determination.POSSIBLY_REQUIRED,
        risk_level=RiskLevel.MEDIUM,
        summary="추가 확인이 필요합니다.",
        rationale="전지 용량 표기가 확인되지 않았습니다.",
    )


def _draft(product: Product | None = None) -> DraftAssessment:
    """규칙 검사를 통과하는 최소 초안. 6개 툴 기록을 모두 채운다."""
    tool_finding = _finding()
    aggregated_finding = tool_finding.model_copy(deep=True)
    records = [
        ToolResult(
            tool_name=name,
            status=ToolStatus.SKIPPED,
            selected=False,
            selection_reason="선택 단계에서 대상이 아니라고 판단했습니다.",
        )
        for name in ToolName
        if name != ToolName.ELECTRICAL
    ]
    records.append(
        ToolResult(
            tool_name=ToolName.ELECTRICAL,
            status=ToolStatus.SUCCESS,
            selected=True,
            selection_reason="전기로 작동합니다.",
            result=ElectricalAssessment(safety_management_required=True),
            findings=[tool_finding],
        )
    )
    return DraftAssessment(
        product=product or Product(product_id="p1"),
        selected_tools=[ToolName.ELECTRICAL],
        tool_results=records,
        findings=[aggregated_finding],
        overall_status=OverallStatus.ACTION_REQUIRED,
        summary="전기안전 항목의 추가 확인이 필요합니다.",
    )


def _tool_record(draft: DraftAssessment, name: ToolName) -> ToolResult:
    return next(result for result in draft.tool_results if result.tool_name is name)


def _unselect_tool(draft: DraftAssessment, name: ToolName) -> None:
    draft.selected_tools = [selected for selected in draft.selected_tools if selected is not name]
    tool_record = _tool_record(draft, name)
    tool_record.selected = False
    tool_record.status = ToolStatus.SKIPPED
    tool_record.result = None
    tool_record.findings = []

    # 미선택으로 변경한 Tool에서 만들어진 종합 finding도 함께 제거한다.
    draft.findings = [
        finding for finding in draft.findings if finding.tool_name is not name
    ]


def _review(**overrides) -> _Review:
    """strict 모드라 모든 필드가 required이므로 기본값을 여기서 채운다."""
    values = {
        "issues": [],
        "additional_tools_required": [],
        "follow_up_questions": [],
        "checked_finding_ids": ["f1"],
    }
    values.update(overrides)
    return _Review(**values)


def _battery_question(required: bool = True) -> _Question:
    return _Question(
        question="전지 용량(Wh)이 표기되어 있습니까?",
        reason="안전확인 대상 판단에 필요합니다.",
        related_tools=[ToolName.ELECTRICAL],
        required=required,
    )


def _unsupported_claim() -> _Issue:
    return _Issue(
        severity="critical",
        issue_type="unsupported_claim",
        description="인용문이 결론을 뒷받침하지 않습니다.",
        related_finding_ids=["f1"],
        recommended_action=None,
    )


def _law_source(**overrides) -> LegalSource:
    values = {
        "source_name": "국가법령정보센터",
        "law_name": "전기용품 및 생활용품 안전관리법",
        "article": "제15조",
        "quoted_text": "안전확인신고를 하여야 한다.",
        "source_url": "https://www.law.go.kr/",
        "is_mock": False,
    }
    values.update(overrides)
    return LegalSource(**values)


@pytest.fixture
def samples() -> SimpleNamespace:
    """초안·검토 응답 도우미.

    draft(product), tool_record(draft, name), unselect_tool(draft, name), review(**overrides),
    battery_question(required), unsupported_claim(), law_source(**overrides).
    """
    return SimpleNamespace(
        draft=_draft,
        tool_record=_tool_record,
        unselect_tool=_unselect_tool,
        review=_review,
        battery_question=_battery_question,
        unsupported_claim=_unsupported_claim,
        law_source=_law_source,
    )
