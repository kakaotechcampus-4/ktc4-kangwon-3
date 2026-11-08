"""다른 Tool이 맡는 법령의 세관장확인 요건을 그 Tool 판단에 맞추는 후처리 (#640)."""

from app.schemas.schemas import (
    CustomsAssessment, Determination, RegulatoryFinding, RiskLevel, ToolName, ToolResult, ToolStatus,
)
from app.tools.customs.related import follow_related_tools

LAW = "전기용품 및 생활용품 안전관리법"
ACTION = f"[「{LAW}」 · HS 8516.79-9000 후보] 이 HS로 분류되면 수입신고 때 세관장확인을 받아야 하고, …"
CITES_ACTION = "[「야생생물 보호 및 관리에 관한 법률(허가)」 · HS 8516.79-9000 후보] …"


def _customs_finding(law: str, action: str) -> RegulatoryFinding:
    return RegulatoryFinding(
        tool_name=ToolName.CUSTOMS, subject=f"세관장확인 대상 후보 — {law}", determination=Determination.POSSIBLY_REQUIRED,
        risk_level=RiskLevel.MEDIUM, summary=f"HS 8516.79-9000로 분류되면 「{law}」 요건을 확인받아야 할 가능성이 있습니다.",
        rationale="결정사례", requirements=[action],
    )


def _customs(*laws: tuple[str, str, ToolName | None]) -> ToolResult:
    """laws: (법령, 할 일, 맡는 Tool). 통관 Tool이 내는 모양 그대로."""
    return ToolResult(
        tool_name=ToolName.CUSTOMS, status=ToolStatus.SUCCESS, selected=True, selection_reason="수입 상품",
        query={"related_tools": {law: tool.value for law, _, tool in laws if tool is not None}},
        result=CustomsAssessment(applicable_requirements=[law for law, _, _ in laws]),
        findings=[_customs_finding(law, action) for law, action, _ in laws],
        required_actions=[action for _, action, _ in laws],
    )


def _tool(name: ToolName, *determinations: Determination, status=ToolStatus.SUCCESS, selected=True) -> ToolResult:
    findings = [RegulatoryFinding(tool_name=name, subject=f"{name.value} 판단 {i}", determination=d,
                                  risk_level=RiskLevel.MEDIUM, summary="요약", rationale="근거")
                for i, d in enumerate(determinations)]
    return ToolResult(tool_name=name, status=status, selected=selected, selection_reason="이유", findings=findings)


def _skipped(name: ToolName) -> ToolResult:
    return ToolResult(tool_name=name, status=ToolStatus.SKIPPED, selected=False, selection_reason="대상 아님")


def _results(customs: ToolResult, *others: ToolResult) -> list[ToolResult]:
    given = {r.tool_name: r for r in (customs, *others)}
    return [given.get(name) or _skipped(name) for name in ToolName]


def test_맡는_Tool이_대상_아님이면_통관_판단도_대상_아님으로_바꾸고_할_일을_뺀다():
    customs = _customs((LAW, ACTION, ToolName.ELECTRICAL))
    results = _results(customs, _tool(ToolName.ELECTRICAL, Determination.NOT_REQUIRED))

    notes = follow_related_tools(results)

    [finding] = customs.findings
    assert (finding.determination, finding.risk_level) == (Determination.NOT_REQUIRED, RiskLevel.LOW)
    assert "전기안전 분야 판단: 대상 아님" in finding.summary
    assert finding.requirements == [] and customs.required_actions == []
    assert customs.result.applicable_requirements == []
    assert customs.query["followed_requirements"] == {LAW: ToolName.ELECTRICAL.value}
    assert notes == [f"「{LAW}」 세관장확인 요건은 같은 법을 판단한 전기안전 분야 결과(대상 아님)를 따랐습니다."]


def test_맡는_Tool이_대상이면_판정을_따르고_세관장확인_할_일은_남긴다():
    customs = _customs((LAW, ACTION, ToolName.ELECTRICAL))
    results = _results(customs, _tool(ToolName.ELECTRICAL, Determination.NOT_REQUIRED, Determination.REQUIRED))

    follow_related_tools(results)

    [finding] = customs.findings
    assert (finding.determination, finding.risk_level) == (Determination.REQUIRED, RiskLevel.MEDIUM)
    assert "대상이면 수입신고 때 세관장확인도 받아야 합니다" in finding.summary
    assert customs.required_actions == [ACTION] and finding.requirements == [ACTION]
    assert customs.result.applicable_requirements == [LAW]


def test_맡는_Tool이_정보_부족이면_정보_부족으로_바꾸고_할_일을_뺀다():
    customs = _customs((LAW, ACTION, ToolName.ELECTRICAL))
    results = _results(customs, _tool(ToolName.ELECTRICAL, Determination.INSUFFICIENT_INFORMATION))

    follow_related_tools(results)

    [finding] = customs.findings
    assert (finding.determination, finding.risk_level) == (Determination.INSUFFICIENT_INFORMATION, RiskLevel.UNKNOWN)
    assert customs.required_actions == []


def test_맡는_Tool이_선택되지_않았거나_실패했으면_그대로_둔다():
    for other in (_skipped(ToolName.ELECTRICAL), _tool(ToolName.ELECTRICAL, status=ToolStatus.FAILED)):
        customs = _customs((LAW, ACTION, ToolName.ELECTRICAL))

        notes = follow_related_tools(_results(customs, other))

        assert notes == []
        assert customs.findings[0].determination is Determination.POSSIBLY_REQUIRED
        assert customs.required_actions == [ACTION]
        assert "followed_requirements" not in customs.query


def test_맡는_Tool이_없는_법령은_그대로_두고_다른_법령만_맞춘다():
    customs = _customs((LAW, ACTION, ToolName.ELECTRICAL),
                       ("야생생물 보호 및 관리에 관한 법률(허가)", CITES_ACTION, None))
    results = _results(customs, _tool(ToolName.ELECTRICAL, Determination.NOT_REQUIRED))

    follow_related_tools(results)

    electrical, cites = customs.findings
    assert electrical.determination is Determination.NOT_REQUIRED
    assert cites.determination is Determination.POSSIBLY_REQUIRED and cites.requirements == [CITES_ACTION]
    assert customs.required_actions == [CITES_ACTION]
    assert customs.result.applicable_requirements == ["야생생물 보호 및 관리에 관한 법률(허가)"]


def test_통관이_선택되지_않았거나_성공하지_않았으면_아무것도_안_한다():
    for customs in (_skipped(ToolName.CUSTOMS),
                    _customs((LAW, ACTION, ToolName.ELECTRICAL)).model_copy(update={"status": ToolStatus.FAILED})):
        assert follow_related_tools(_results(customs, _tool(ToolName.ELECTRICAL, Determination.NOT_REQUIRED))) == []


def test_실제_통관_결과를_종합한_뒤에도_규칙_검사를_통과한다():
    # 전기 Tool이 '대상 아님'이면 통관의 전안법 판단이 확정 판단(대상 아님)으로 바뀌는데, 규칙 검사는 확정 판단에
    # 근거를 요구한다. 통관 판단이 들고 있던 관세법·고시 근거가 그대로 남아 통과해야 한다
    from app.agents.verification import VerificationAgent
    from app.pipeline.aggregator import ResultAggregator
    from app.schemas.agent import ToolSelectionItem, ToolSelectionResponse
    from app.schemas.pipeline import SelectionResult
    from app.schemas.schemas import ElectricalAssessment, LegalSource
    from .test_tool import product_and_facts, review, run, select

    product, facts = product_and_facts()
    customs, _, _, _ = run(product, facts, review(select()))
    source = LegalSource(source_name="법제처 국가법령정보", law_name=LAW, article="제3조", quoted_text="인용",
                         source_url="https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=1", effective_date="20250101",
                         is_mock=False)
    electrical = ToolResult(
        tool_name=ToolName.ELECTRICAL, status=ToolStatus.SUCCESS, selected=True, selection_reason="전기",
        result=ElectricalAssessment(safety_management_required=False),
        findings=[RegulatoryFinding(tool_name=ToolName.ELECTRICAL, subject="안전확인 대상",
                                    determination=Determination.NOT_REQUIRED, risk_level=RiskLevel.LOW,
                                    summary="대상 아님", rationale="품목표에 없음", legal_sources=[source])])
    results = _results(customs, electrical)
    selection = SelectionResult(
        selection=ToolSelectionResponse(decisions=[
            ToolSelectionItem(tool_name=r.tool_name, selected=r.selected, reason="이유") for r in results]),
        tool_results=results, tool_result_history=[customs, electrical])

    draft = ResultAggregator().aggregate(product, selection)
    rules = VerificationAgent(None).verify_rules(draft)

    customs_finding = next(f for f in draft.findings if f.tool_name is ToolName.CUSTOMS)
    assert customs_finding.determination is Determination.NOT_REQUIRED and customs_finding.legal_sources
    assert draft.required_actions == []
    assert [(issue.issue_type.value, issue.description) for issue in rules.issues] == []
    assert rules.additional_tools_required == []
