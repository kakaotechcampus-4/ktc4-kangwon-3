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
        tool_name=ToolName.CUSTOMS, subject=f"세관 확인 서류가 필요할 수 있음 — {law}", determination=Determination.POSSIBLY_REQUIRED,
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
    # 대상이 아니면 제목도 "필요 없음"으로 바뀌어 본문과 어긋나지 않음
    assert finding.subject == f"세관 확인 서류 필요 없음 — {LAW}"
    assert finding.summary == "- 전기안전 분야 판단을 따릅니다: 대상 아님\n- 통관 서류도 필요하지 않습니다"
    # 다시 불려도 바뀐 제목으로 같은 판단을 찾아 결과가 같음
    follow_related_tools(results)
    assert finding.subject == f"세관 확인 서류 필요 없음 — {LAW}" and finding.requirements == []
    assert finding.requirements == [] and customs.required_actions == []
    assert customs.result.applicable_requirements == []
    assert customs.query["followed_requirements"] == {LAW: ToolName.ELECTRICAL.value}
    assert notes == [f"「{LAW}」 세관장확인 요건은 같은 법을 판단한 전기안전 분야 결과(대상 아님)를 따랐습니다."]


def test_따라서_마지막_요건이_빠지면_세관장확인_필요_칸을_false로_맞춘다():
    # #797: 전기 Tool이 대상 아님 → 통관 판단도 "필요 없음"인데 칸이 null로 남지 않게
    customs = _customs((LAW, ACTION, ToolName.ELECTRICAL))
    customs.query.update(hs_candidates=["8516799000"], requirements={"8516799000": [LAW]})
    follow_related_tools(_results(customs, _tool(ToolName.ELECTRICAL, Determination.NOT_REQUIRED)))
    assert customs.result.customs_confirmation_required is False


def test_따른_뒤에도_요건이_남으면_세관장확인_필요_칸은_그대로_둔다():
    other = "수입식품안전관리 특별법"
    customs = _customs((LAW, ACTION, ToolName.ELECTRICAL), (other, f"[「{other}」] …", None))
    customs.query.update(hs_candidates=["8516799000"], requirements={"8516799000": [LAW, other]})
    follow_related_tools(_results(customs, _tool(ToolName.ELECTRICAL, Determination.NOT_REQUIRED)))
    assert customs.result.applicable_requirements == [other]
    assert customs.result.customs_confirmation_required is None


def test_맡는_Tool이_대상이면_판정을_따르고_세관장확인_할_일은_남긴다():
    customs = _customs((LAW, ACTION, ToolName.ELECTRICAL))
    results = _results(customs, _tool(ToolName.ELECTRICAL, Determination.NOT_REQUIRED, Determination.REQUIRED))

    follow_related_tools(results)

    [finding] = customs.findings
    assert (finding.determination, finding.risk_level) == (Determination.REQUIRED, RiskLevel.MEDIUM)
    # 대상이면 제목도 "필요"로 바뀌어 본문과 어긋나지 않음 (리뷰 #759)
    assert finding.subject == f"세관 확인 서류 필요 — {LAW}"
    assert finding.summary == "- 전기안전 분야 판단을 따릅니다: 대상\n- 통관 때도 서류를 내야 합니다"
    follow_related_tools(results)
    assert finding.subject == f"세관 확인 서류 필요 — {LAW}" and customs.required_actions == [ACTION]
    assert customs.required_actions == [ACTION] and finding.requirements == [ACTION]
    assert customs.result.applicable_requirements == [LAW]


def test_맡는_Tool이_정보_부족이면_통관_요건을_그대로_둔다():
    # 판단하지 못한 것이지 대상이 아닌 것이 아니다. 실사이트 전동 클렌저(11/9): 전기 Tool이 정격 전압을 몰라
    # 정보 부족으로 끝났는데 전안법 세관장확인 서류 안내까지 사라짐
    for tool, law in ((ToolName.ELECTRICAL, LAW), (ToolName.CHILDREN, "어린이제품 안전 특별법")):
        action = f"[「{law}」 · HS 8543.70-9090 후보] …"
        customs = _customs((law, action, tool))

        notes = follow_related_tools(_results(customs, _tool(tool, Determination.INSUFFICIENT_INFORMATION)))

        [finding] = customs.findings
        assert notes == []
        assert (finding.determination, finding.risk_level) == (Determination.POSSIBLY_REQUIRED, RiskLevel.MEDIUM)
        assert finding.requirements == [action] and customs.required_actions == [action]
        assert "followed_requirements" not in customs.query


def test_대상_아님과_정보_부족이_섞이면_따르지_않는다():
    # 판단 여러 개 중 하나라도 정하지 못했으면 '대상 아님'으로 모으지 않는다
    customs = _customs((LAW, ACTION, ToolName.ELECTRICAL))
    results = _results(customs, _tool(ToolName.ELECTRICAL, Determination.NOT_REQUIRED,
                                      Determination.INSUFFICIENT_INFORMATION))

    assert follow_related_tools(results) == []
    assert customs.required_actions == [ACTION]


def test_전파_Tool이_정보_부족이면_전파법_요건을_그대로_둔다():
    # 전파 Tool은 무선 기능만 본다. 무선 기능을 못 찾아 낸 정보 부족은 유선 전자파적합성까지 비대상이라는 뜻이 아니다
    # (리뷰 #708: 유선 전기제품에서 전자파적합성 안내가 사라짐)
    radio_action = "[「전파법」 · HS 8516.31-0000 후보] …"
    customs = _customs(("전파법", radio_action, ToolName.RADIO))

    notes = follow_related_tools(_results(customs, _tool(ToolName.RADIO, Determination.INSUFFICIENT_INFORMATION)))

    [finding] = customs.findings
    assert notes == []
    assert (finding.determination, finding.requirements) == (Determination.POSSIBLY_REQUIRED, [radio_action])
    assert customs.required_actions == [radio_action]
    assert "followed_requirements" not in customs.query


def test_전파_Tool이_후보를_냈으면_전파법_요건이_그_판단을_따른다():
    radio_action = "[「전파법」 · HS 8517.62-0000 후보] …"
    customs = _customs(("전파법", radio_action, ToolName.RADIO))

    notes = follow_related_tools(_results(customs, _tool(ToolName.RADIO, Determination.POSSIBLY_REQUIRED)))

    [finding] = customs.findings
    assert finding.summary == "- 전파 분야 판단을 따릅니다: 대상 후보\n- 대상이면 통관 때도 서류를 내야 합니다"
    assert customs.required_actions == [radio_action]
    assert notes == ["「전파법」 세관장확인 요건은 같은 법을 판단한 전파 분야 결과(대상 후보)를 따랐습니다."]


def test_식약_법령은_식약_Tool_판단을_따르지_않고_그대로_둔다():
    # 식약 Tool 하나가 식품, 화장품, 의료기기 법령을 모두 맡는다. 의료기기 '품목 미확인' 하나로 수입식품법, 화장품법
    # 요건까지 정보 부족으로 바뀌던 문제 (리뷰 #708). 분야별로 맞추는 일은 #707
    for determination in (Determination.INSUFFICIENT_INFORMATION, Determination.POSSIBLY_REQUIRED):
        laws = [("수입식품안전관리 특별법", "[수입식품법] …", ToolName.FOOD_DRUG), ("화장품법", "[화장품법] …", ToolName.FOOD_DRUG)]
        customs = _customs(*laws)
        summaries = [finding.summary for finding in customs.findings]

        notes = follow_related_tools(_results(customs, _tool(ToolName.FOOD_DRUG, determination)))

        assert notes == []
        assert [finding.determination for finding in customs.findings] == [Determination.POSSIBLY_REQUIRED] * 2
        assert [finding.summary for finding in customs.findings] == summaries
        assert customs.required_actions == ["[수입식품법] …", "[화장품법] …"]


def test_통관_판단_제목은_통관_Tool과_같은_함수로_만든다():
    # 제목 형식이 바뀌면 맞출 판단을 못 찾고 조용히 넘어간다 (리뷰 #708)
    from app.tools.customs.rules import requirement_subject

    assert _customs_finding(LAW, ACTION).subject == requirement_subject(LAW) == f"세관 확인 서류가 필요할 수 있음 — {LAW}"


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
