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

RESULT_KINDS = {
    ToolName.CUSTOMS: "customs",
    ToolName.RADIO: "radio",
    ToolName.FOOD_DRUG: "food_drug",
    ToolName.ELECTRICAL: "electrical",
    ToolName.CHILDREN: "children",
    ToolName.LABEL_AD: "advertising",
}

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
        # 상세 결과 kind가 툴 종류와 다름 (스키마 판별 유니온은 이 일치까지는 검사 안 함)
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
    # 관세·표시광고는 불리언 신호 하나로 강제하지 않아 제외 (기본 실행 정책은 선택·파이프라인과 합의 필요)
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
        # 신호가 명시적으로 True인데 툴 미선택 (적용 확정이 아니라 누락 후보 경고)
        if any(value is True for value in values) and name not in draft.selected_tools:
            context.add(
                IssueType.MISSING_TOOL,
                f"{name}: 상품에 검토 신호가 있으나 툴이 선택되지 않았습니다. "
                "적용 여부를 추가 검토하세요.",
                tool=name,
                severity="warning",
            )

    # 연령 표기는 있는데 어린이 대상 판단이 None이고 어린이 툴 미선택 ("성인용" 등 오탐 때문에 target_age만으로는 안 잡음)
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

    for finding in draft.findings:
        finding_id = finding.finding_id
        # 종합 판단이 툴 원본과 다름 (aggregate는 원본 finding을 바꾸지 않는 계약)
        if finding_id not in original or original[finding_id] != finding:
            context.add(
                IssueType.CONTRADICTION,
                "종합 판단이 원래 툴 판단과 일치하지 않습니다.",
                (finding_id,),
            )
        # 확정 판단(필요·불필요·해당 없음)만 근거 필수. 가능성·정보 부족은 제외
        if finding.determination in DEFINITIVE:
            cited = [
                source
                for source in finding.legal_sources
                if (source.quoted_text or "").strip()
                and (source.source_url or "").strip()
            ]
            usable = [source for source in cited if not source.is_mock]
            # 인용문+출처를 갖춘 근거가 하나도 없음 → 툴 재실행 요청
            if not cited:
                context.add(
                    IssueType.MISSING_EVIDENCE,
                    "확정적 판단에 인용문과 출처가 없습니다. "
                    "URL만으로는 검증할 수 없습니다.",
                    (finding_id,),
                    finding.tool_name,
                )
            # 근거가 mock뿐 → 재실행해도 안 바뀌어 경고만 (실자료가 오면 자동 해소)
            elif not usable:
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
