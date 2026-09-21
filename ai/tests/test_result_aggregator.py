"""ResultAggregator의 조립·상태 계산 규칙을 검증한다."""

import pytest

from app.pipeline.aggregator import ResultAggregator
from app.schemas.agent import SelectionResult, ToolSelectionItem, ToolSelectionResponse
from app.schemas.product import Product
from app.schemas.schemas import (
    Determination,
    OverallStatus,
    RegulatoryFinding,
    RiskLevel,
    ToolName,
    ToolResult,
    ToolStatus,
)


def _finding(
    *,
    determination: Determination = Determination.NOT_REQUIRED,
    risk_level: RiskLevel = RiskLevel.LOW,
    assumptions: list[str] | None = None,
) -> RegulatoryFinding:
    return RegulatoryFinding(
        tool_name=ToolName.ELECTRICAL,
        subject="전기안전 심사",
        determination=determination,
        risk_level=risk_level,
        summary="심사 결과",
        rationale="Tool이 확인한 근거",
        assumptions=assumptions or [],
    )


def _selection_result(*selected_results: ToolResult) -> SelectionResult:
    by_name = {result.tool_name: result for result in selected_results}
    decisions = [
        ToolSelectionItem(
            tool_name=name,
            selected=name in by_name,
            reason=f"{name.value} 선택 이유",
        )
        for name in ToolName
    ]
    tool_results = [
        by_name.get(name)
        or ToolResult(
            tool_name=name,
            status=ToolStatus.SKIPPED,
            selected=False,
            selection_reason=f"{name.value} 미선택 이유",
        )
        for name in ToolName
    ]
    return SelectionResult(
        selection=ToolSelectionResponse(decisions=decisions),
        tool_results=tool_results,
        tool_result_history=[result.model_copy(deep=True) for result in selected_results],
    )


def _tool_result(
    *,
    status: ToolStatus = ToolStatus.SUCCESS,
    findings: list[RegulatoryFinding] | None = None,
    required_actions: list[str] | None = None,
    missing_information: list[str] | None = None,
) -> ToolResult:
    return ToolResult(
        tool_name=ToolName.ELECTRICAL,
        status=status,
        selected=True,
        selection_reason="전기 사용 상품",
        findings=findings or [],
        required_actions=required_actions or [],
        missing_information=missing_information or [],
    )


def test_선택_결과와_Tool_결과를_DraftAssessment로_조립한다():
    finding = _finding(
        determination=Determination.REQUIRED,
        risk_level=RiskLevel.MEDIUM,
        assumptions=["상품 표기가 정확함", "상품 표기가 정확함"],
    )
    selection_result = _selection_result(
        _tool_result(
            findings=[finding],
            required_actions=["KC 인증 확인", "KC 인증 확인"],
            missing_information=["전지 용량", "전지 용량"],
        )
    )
    product = Product(product_id="p1", product_name="무선 이어폰")

    draft = ResultAggregator().aggregate(product, selection_result)

    assert draft.product == product
    assert draft.product is not product
    assert draft.selected_tools == [ToolName.ELECTRICAL]
    assert len(draft.tool_results) == len(ToolName)
    assert draft.findings == [finding]
    assert draft.findings[0] is not finding
    assert draft.required_actions == ["KC 인증 확인"]
    assert draft.missing_information == ["전지 용량"]
    assert draft.assumptions == ["상품 표기가 정확함"]
    assert draft.follow_up_questions == []
    assert draft.summary == "선택 Tool 1개 중 성공 1개, 미완료 0개이며 판단 1건을 수집했습니다."


def test_초안을_변경해도_원본_선택_결과는_변하지_않는다():
    selection_result = _selection_result(_tool_result(findings=[_finding()]))
    product = Product(product_id="p1", product_name="원본")

    draft = ResultAggregator().aggregate(product, selection_result)
    draft.product.product_name = "변경됨"
    draft_tool_result = next(
        result
        for result in draft.tool_results
        if result.tool_name is ToolName.ELECTRICAL
    )
    draft_tool_result.selection_reason = "변경됨"
    draft.findings[0].summary = "변경됨"

    original_result = next(
        result
        for result in selection_result.tool_results
        if result.tool_name is ToolName.ELECTRICAL
    )
    assert product.product_name == "원본"
    assert original_result.selection_reason == "전기 사용 상품"
    assert original_result.findings[0].summary == "심사 결과"


@pytest.mark.parametrize(
    ("tool_result", "expected"),
    [
        (
            _tool_result(
                findings=[_finding(risk_level=RiskLevel.HIGH)],
                missing_information=["정격 정보"],
            ),
            OverallStatus.HIGH_RISK,
        ),
        (
            _tool_result(
                findings=[_finding(determination=Determination.REQUIRED)],
                missing_information=["정격 정보"],
            ),
            OverallStatus.ACTION_REQUIRED,
        ),
        (
            _tool_result(findings=[_finding(risk_level=RiskLevel.MEDIUM)]),
            OverallStatus.ACTION_REQUIRED,
        ),
        (
            _tool_result(
                findings=[_finding(determination=Determination.POSSIBLY_REQUIRED,)]
            ),
            OverallStatus.ACTION_REQUIRED,
        ),
        (
            _tool_result(status=ToolStatus.FAILED),
            OverallStatus.INSUFFICIENT_INFORMATION,
        ),
        (
            _tool_result(missing_information=["정격 정보"]),
            OverallStatus.INSUFFICIENT_INFORMATION,
        ),
        (
            _tool_result(findings=[_finding()]),
            OverallStatus.LIKELY_COMPLIANT,
        ),
    ],
)
def test_확인된_위험과_조치를_정보_부족보다_먼저_반영한다(tool_result, expected):
    draft = ResultAggregator().aggregate(
        Product(product_id="p1"),
        _selection_result(tool_result),
    )

    assert draft.overall_status is expected


def test_중복_finding을_제거하지_않아_검증_단계가_발견할_수_있게_한다():
    finding = _finding()
    tool_result = _tool_result(
        findings=[finding, finding.model_copy(deep=True)],
    )

    draft = ResultAggregator().aggregate(
        Product(product_id="p1"),
        _selection_result(tool_result),
    )

    assert len(draft.findings) == 2
    assert draft.findings[0].finding_id == draft.findings[1].finding_id


def test_모든_Tool이_미선택되어_finding이_없으면_정보_부족으로_판정한다():
    draft = ResultAggregator().aggregate(
        Product(product_id="p1"),
        _selection_result(),
    )

    assert draft.selected_tools == []
    assert draft.findings == []
    assert draft.overall_status is OverallStatus.INSUFFICIENT_INFORMATION


def test_선택된_Tool이_finding을_반환하지_않으면_정보_부족으로_판정한다():
    draft = ResultAggregator().aggregate(
        Product(product_id="p1"),
        _selection_result(
            _tool_result(
                status=ToolStatus.SUCCESS,
                findings=[],
            )
        ),
    )

    assert draft.selected_tools == [ToolName.ELECTRICAL]
    assert draft.findings == []
    assert draft.overall_status is OverallStatus.INSUFFICIENT_INFORMATION