"""다른 규제 Tool이 맡는 법령의 세관장확인 요건을 그 Tool의 판단에 맞춘다 (#640).

세관장확인 API는 요건을 HS 단위로 줘서, 전안법·전파법·식품법처럼 다른 Tool이 제품 단위로 판단하는 법령이
해당 없는 상품에도 딸려 온다 (예: 플라스틱 폰케이스 HS에 수입식품법·위생용품관리법·전안법). 통관 Tool은 다른
Tool과 병렬로 돌아 그 결과를 볼 수 없으므로, 종합 단계가 Tool 결과를 모은 뒤 여기서 맞춘다.

- 그 Tool이 선택돼 성공했으면: 통관 판단의 판정을 그 Tool 판단으로 바꾸고, 대상이 아니거나 정보 부족이면 할 일을 뺀다.
  판단 자체는 남긴다 (성공한 Tool의 판단이 비면 검증 규칙이 Tool 실패로 보고 재실행을 요청함).
- 그 Tool이 선택되지 않았거나 실패했으면: 그대로 둔다. 전파법처럼 Tool 범위(무선 기능)보다 법 범위(전자파 적합성)가
  넓은 경우가 있어, 선택되지 않았다고 요건을 빼지 않는다.
"""

from ...schemas.schemas import Determination, RegulatoryFinding, RiskLevel, ToolName, ToolResult, ToolStatus

_TOOL_LABELS = {
    ToolName.ELECTRICAL: "전기안전", ToolName.RADIO: "전파", ToolName.CHILDREN: "어린이제품", ToolName.FOOD_DRUG: "식약",
}
# 통관 판단에 옮길 때의 위험도. 대상·후보는 통관 판단의 원래 위험도(보통)를 유지
_RISK_OF = {Determination.NOT_REQUIRED: RiskLevel.LOW, Determination.NOT_APPLICABLE: RiskLevel.LOW,
            Determination.INSUFFICIENT_INFORMATION: RiskLevel.UNKNOWN}
_LABEL_OF = {Determination.REQUIRED: "대상", Determination.POSSIBLY_REQUIRED: "대상 후보",
             Determination.NOT_REQUIRED: "대상 아님", Determination.NOT_APPLICABLE: "해당 없음",
             Determination.INSUFFICIENT_INFORMATION: "정보 부족"}
# 할 일을 남길 판정. 나머지(대상 아님·해당 없음·정보 부족)는 세관장확인 서류 안내를 뺀다
_KEEP_ACTIONS = {Determination.REQUIRED, Determination.POSSIBLY_REQUIRED}


def follow_related_tools(tool_results: list[ToolResult]) -> list[str]:
    """통관 결과의 법령별 판단을 그 법령을 맡는 Tool의 판단에 맞춘다. tool_results를 그 자리에서 고친다.

    Args:
        tool_results: 종합 단계가 복사한 Tool 결과 6개.

    Returns:
        list[str]: 맞춘 법령마다 남길 가정 문장. 맞춘 게 없으면 빈 목록.
    """
    by_name = {result.tool_name: result for result in tool_results}
    customs = by_name.get(ToolName.CUSTOMS)
    if customs is None or not customs.selected or customs.status is not ToolStatus.SUCCESS:
        return []
    related: dict[str, str] = customs.query.get("related_tools") or {}
    notes: list[str] = []
    followed: dict[str, str] = {}
    for law_name, tool_value in related.items():
        tool = ToolName(tool_value)
        other = by_name.get(tool)
        if other is None or not other.selected or other.status is not ToolStatus.SUCCESS or not other.findings:
            continue
        verdict = _verdict(other.findings)
        finding = next((f for f in customs.findings if f.subject == f"세관장확인 대상 후보 — {law_name}"), None)
        if verdict is None or finding is None:
            continue
        label = _TOOL_LABELS.get(tool, tool.value)
        _apply(customs, finding, law_name, verdict, label)
        followed[law_name] = tool_value
        notes.append(f"「{law_name}」 세관장확인 요건은 같은 법을 판단한 {label} 분야 결과({_LABEL_OF[verdict]})를 따랐습니다.")
    if followed:
        customs.query["followed_requirements"] = followed
    return notes


def _verdict(findings: list[RegulatoryFinding]) -> Determination | None:
    """Tool 판단 여러 개를 하나로 모은다. 대상 > 대상 후보 > 정보 부족 > 대상 아님·해당 없음 순으로 센다."""
    determinations = {finding.determination for finding in findings}
    for candidate in (Determination.REQUIRED, Determination.POSSIBLY_REQUIRED, Determination.INSUFFICIENT_INFORMATION):
        if candidate in determinations:
            return candidate
    if determinations and determinations <= {Determination.NOT_REQUIRED, Determination.NOT_APPLICABLE}:
        return Determination.NOT_REQUIRED
    return None


def _apply(customs: ToolResult, finding: RegulatoryFinding, law_name: str, verdict: Determination, label: str) -> None:
    """통관 판단 하나의 판정·요약·할 일을 다른 Tool 판단에 맞춘다."""
    finding.determination = verdict
    finding.risk_level = _RISK_OF.get(verdict, finding.risk_level)
    finding.summary = (f"「{law_name}」 세관장확인 요건은 {label} 분야 판단을 따릅니다. {label} 분야 판단: {_LABEL_OF[verdict]}."
                       + (" 대상이면 수입신고 때 세관장확인도 받아야 합니다." if verdict in _KEEP_ACTIONS else
                          " 세관장확인 서류 준비 안내는 내지 않습니다."))
    if verdict in _KEEP_ACTIONS:
        return
    dropped = set(finding.requirements)
    finding.requirements = []
    customs.required_actions = [action for action in customs.required_actions if action not in dropped]
    if customs.result is not None and hasattr(customs.result, "applicable_requirements"):
        customs.result.applicable_requirements = [name for name in customs.result.applicable_requirements
                                                  if name != law_name]
