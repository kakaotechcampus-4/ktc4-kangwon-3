"""검증 규칙 검사. 모델 없이 심사 초안의 구조·근거 유무만 봄 (VerificationAgent.verify_rules가 사용)."""

from dataclasses import dataclass, field
from typing import Literal

from ...schemas.schemas import (
    Determination,
    DraftAssessment,
    RegulatoryFinding,
    ToolName,
    ToolStatus,
    VerificationIssue,
    VerificationIssueType as IssueType,
)

# 상세 결과의 kind와 툴 종류의 대응. 판별 유니온이 둘의 일치까지 검사하지는 않는다.
RESULT_KINDS = {
    ToolName.CUSTOMS: "customs",
    ToolName.RADIO: "radio",
    ToolName.FOOD_DRUG: "food_drug",
    ToolName.ELECTRICAL: "electrical",
    ToolName.CHILDREN: "children",
    ToolName.LABEL_AD: "advertising",
}

# 확정적 판단은 실자료 근거가 있어야 한다. 정보 부족·가능성 판단은 대상이 아니다.
DEFINITIVE = frozenset(
    {Determination.REQUIRED, Determination.NOT_REQUIRED, Determination.NOT_APPLICABLE}
)


Severity = Literal["critical", "warning", "info"]


@dataclass
class RuleCheckContext:
    """규칙 검사가 찾은 이슈와 재실행할 툴을 순서대로 모은다.

    Attributes:
        issues: 발견한 이슈.
        additional_tools: 재실행할 툴. 중복 없음.
    """

    issues: list[VerificationIssue] = field(default_factory=list)
    additional_tools: list[ToolName] = field(default_factory=list)

    def add(
        self,
        kind: IssueType,
        text: str,
        ids: tuple[str, ...] = (),
        tool: ToolName | None = None,
        severity: Severity = "critical",
    ) -> None:
        """이슈 하나를 추가하고, tool이 있으면 재실행 목록에 넣는다.

        Args:
            kind: 이슈 종류.
            text: 설명.
            ids: 관련 finding ID.
            tool: 재실행할 툴. None이면 추가 안 함.
            severity: 심각도.
        """
        self.issues.append(
            VerificationIssue(
                severity=severity,
                issue_type=kind,
                description=text,
                related_finding_ids=list(ids),
                recommended_action="관련 입력과 툴 결과를 보완한 뒤 다시 검증하세요.",
            )
        )
        if tool is not None and tool not in self.additional_tools:
            self.additional_tools.append(tool)


def check_tool_consistency(
    draft: DraftAssessment,
    context: RuleCheckContext,
) -> None:
    """툴 선택 목록과 실행 기록이 서로 맞는지 검사한다.

    Args:
        draft: 검증할 심사 초안.
        context: 이슈를 모을 곳.
    """
    records = {result.tool_name: result for result in draft.tool_results}
    if len(records) != len(draft.tool_results):
        context.add(IssueType.CONTRADICTION, "같은 툴의 실행 기록이 중복되었습니다.")
    if len(set(draft.selected_tools)) != len(draft.selected_tools):
        context.add(IssueType.CONTRADICTION, "선택 툴 목록에 중복이 있습니다.")

    for name in ToolName:
        tool_record = records.get(name)
        if tool_record is None:
            context.add(
                IssueType.MISSING_TOOL,
                f"{name}: 선택·미선택 실행 기록이 없습니다.",
                tool=name if name in draft.selected_tools else None,
            )
            continue
        if tool_record.selected != (name in draft.selected_tools):
            context.add(
                IssueType.CONTRADICTION,
                f"{name}: 선택 목록과 실행 기록의 selected가 다릅니다.",
            )
        if tool_record.selected:
            if tool_record.status != ToolStatus.SUCCESS:
                context.add(
                    IssueType.TOOL_FAILURE,
                    f"{name}: 선택된 툴이 성공 상태가 아닙니다.",
                    tool=name,
                )
            elif tool_record.result is None or not tool_record.findings:
                context.add(
                    IssueType.TOOL_FAILURE,
                    f"{name}: 성공 기록에 상세 결과 또는 판단이 없습니다.",
                    tool=name,
                )
        else:
            if tool_record.status != ToolStatus.SKIPPED:
                context.add(
                    IssueType.CONTRADICTION,
                    f"{name}: 미선택 툴의 실행 상태가 skipped가 아닙니다.",
                )
            if tool_record.result is not None or tool_record.findings:
                context.add(
                    IssueType.CONTRADICTION,
                    f"{name}: 미선택 툴에 실행 결과 또는 판단이 들어 있습니다.",
                )
        if tool_record.result is not None and tool_record.result.kind != RESULT_KINDS[name]:
            context.add(
                IssueType.CONTRADICTION,
                f"{name}: 상세 결과 kind가 툴 종류와 다릅니다.",
            )


def check_required_tools(
    draft: DraftAssessment,
    context: RuleCheckContext,
) -> None:
    """상품 신호가 있는데 해당 툴이 선택되지 않았는지 검사한다.

    Args:
        draft: 검증할 심사 초안.
        context: 이슈를 모을 곳.
    """
    # True인 명시적 신호만 후보 누락 검사에 쓴다. 규제 적용을 확정하는 규칙이 아니다.
    # CUSTOMS와 LABEL_AD는 단순 불리언 하나로 강제하지 않는다. 기본 실행 정책이 필요하면
    # selection·pipeline 담당자와 합의해 별도의 정책으로 추가해야 한다.
    product = draft.product
    signals: dict[ToolName, list[bool | None]] = {
        ToolName.RADIO: [product.wireless_comm, product.wireless_charging],
        ToolName.ELECTRICAL: [
            product.electrical_powered,
            product.battery_included,
            product.battery_is_the_product,
        ],
        ToolName.CHILDREN: [product.for_children],
        ToolName.FOOD_DRUG: [
            product.food_contact,
            product.medical_claim,
            product.cosmetic_claim,
        ],
    }
    for name, values in signals.items():
        if any(value is True for value in values) and name not in draft.selected_tools:
            context.add(
                IssueType.MISSING_TOOL,
                f"{name}: 상품에 검토 신호가 있으나 툴이 선택되지 않았습니다. "
                "적용 여부를 추가 검토하세요.",
                tool=name,
                severity="warning",
            )

    # for_children은 연령 표기뿐 아니라 광고 맥락까지 해석한 값이라,
    # 판단이 서지 않으면 null로 남는다. target_age만 보면 "성인용"·"만 14세 이상"까지
    # 걸리므로 연령 표기가 있으면서 for_children이 None일 때만 잡는다.
    if (
        product.for_children is None
        and (product.target_age or "").strip()
        and ToolName.CHILDREN not in draft.selected_tools
    ):
        context.add(
            IssueType.INSUFFICIENT_PRODUCT_DATA,
            f"연령 표기 '{product.target_age}'가 있으나 어린이 대상 여부가 판단되지 "
            "않았습니다. 어린이제품 적용 여부를 확인하세요.",
            severity="warning",
        )


def check_findings(
    draft: DraftAssessment,
    context: RuleCheckContext,
) -> None:
    """종합 판단이 툴 원본 판단과 같은지, 확정 판단에 근거가 있는지 검사한다.

    Args:
        draft: 검증할 심사 초안.
        context: 이슈를 모을 곳.
    """
    final_ids = [finding.finding_id for finding in draft.findings]
    if len(final_ids) != len(set(final_ids)):
        context.add(IssueType.CONTRADICTION, "종합 판단의 finding_id가 중복되었습니다.")
    if not final_ids:
        context.add(IssueType.MISSING_EVIDENCE, "검증할 종합 판단이 없습니다.")

    # 툴이 만든 원본 판단을 모아 종합 결과와 대조한다.
    original: dict[str, RegulatoryFinding] = {}
    for tool_record in draft.tool_results:
        for finding in tool_record.findings:
            if finding.finding_id in original or finding.tool_name != tool_record.tool_name:
                context.add(
                    IssueType.CONTRADICTION,
                    "툴 판단의 ID 중복 또는 소속 툴 불일치가 있습니다.",
                )
            original[finding.finding_id] = finding
    for dropped in sorted(original.keys() - set(final_ids)):
        context.add(
            IssueType.CONTRADICTION,
            f"툴 판단 {dropped}가 종합 결과에서 누락되었습니다.",
        )

    # DraftAssessment.findings는 도구 판단의 출처 보존용 목록이다. aggregate 단계는
    # overall_status·summary·required_actions를 종합하되 원본 finding을 변경하지 않는다.
    # 이 계약을 바꾸려면 원본과 종합 판단을 별도 필드로 분리하는 스키마 합의가 먼저 필요하다.
    for finding in draft.findings:
        finding_id = finding.finding_id
        if finding_id not in original or original[finding_id] != finding:
            context.add(
                IssueType.CONTRADICTION,
                "종합 판단이 원래 툴 판단과 일치하지 않습니다.",
                (finding_id,),
            )
        if finding.determination in DEFINITIVE:
            # "근거가 없다"와 "근거는 있는데 mock이다"는 서로 다른 문제다.
            cited = [
                source
                for source in finding.legal_sources
                if (source.quoted_text or "").strip()
                and (source.source_url or "").strip()
            ]
            usable = [source for source in cited if not source.is_mock]
            if not cited:
                context.add(
                    IssueType.MISSING_EVIDENCE,
                    "확정적 판단에 인용문과 출처가 없습니다. "
                    "URL만으로는 검증할 수 없습니다.",
                    (finding_id,),
                    finding.tool_name,
                )
            elif not usable:
                # 툴이 실자료를 돌려주면 is_mock=False가 되어 이 지적은 저절로 사라진다.
                # 같은 툴을 재실행해도 mock 여부는 바뀌지 않으므로 툴 재실행을 요구하지 않는다.
                context.add(
                    IssueType.MISSING_EVIDENCE,
                    "확정적 판단의 근거가 mock 자료뿐입니다. "
                    "실자료로 확인하기 전에는 확정 판단으로 쓸 수 없습니다.",
                    (finding_id,),
                    severity="warning",
                )


def run_rule_checks(draft: DraftAssessment) -> RuleCheckContext:
    """규칙 검사 3종(툴 정합성·필수 툴·판단 근거)을 차례로 실행한다.

    Args:
        draft: 검증할 심사 초안.

    Returns:
        RuleCheckContext: 발견한 이슈와 재실행할 툴.
    """
    context = RuleCheckContext()
    check_tool_consistency(draft, context)
    check_required_tools(draft, context)
    check_findings(draft, context)
    return context
