"""진단 결과(FinalAssessment)를 BE에 보낼 공개 진단서(PublicAssessmentDto)로 바꾼다.

콜백 이벤트 생성기가 받는 AssessmentPresenter 형식(assessment(result))을 그대로 따른다. 서버 조립에서 더미 변환기 대신 끼운다.
- 결과 상태: status.decide_result_status
- 분야 카드: 6개 분야를 모두 보냄(선택 안 된 분야는 SKIPPED). 판단은 그대로 옮기고 BE 칸 길이를 넘으면 자른다.
- 할 일: 계약상 진단서 한 목록. 분야 순서로 모으고, 품목·판매 방식은 문장 앞 라벨로 구분된다.
- 안내: 미완료 사유, 질문으로 묻지 않은 부족 정보, 고정 안내.
"""

from ..schemas.callback import (
    PublicAssessmentDto, PublicFindingDto, PublicLegalSourceDto, PublicToolReviewDto,
)
from ..schemas.schemas import (
    ExecutionEndReason, FinalAssessment, LegalSource, RegulatoryFinding, ToolName, ToolResult, ToolStatus,
)
from .status import DecisionReason, ResultDecision, decide_result_status, is_completed, tool_order

# BE 수신 DTO·DB 칸 길이 
SUBJECT_MAX = 255
SOURCE_FIELD_MAX = 255
EFFECTIVE_DATE_MAX = 50

DISCLAIMER = "법령 근거에 따른 참고 정보이며 법률 자문이나 확정 판단이 아닙니다."

# 요약 문장에 쓰는 분야 이름
FIELD_LABELS = {
    ToolName.CUSTOMS: "통관",
    ToolName.RADIO: "전파",
    ToolName.FOOD_DRUG: "식품·의약품",
    ToolName.ELECTRICAL: "전기용품",
    ToolName.CHILDREN: "어린이제품",
    ToolName.LABEL_AD: "표시·광고",
}

_CARD_STATUS = {ToolStatus.SUCCESS: "COMPLETED", ToolStatus.SKIPPED: "SKIPPED"}
_SKIPPED_MESSAGE = "이 상품에 해당하지 않는 분야로 판단해 검토하지 않았습니다."
_INCOMPLETE_MESSAGE = "이 분야 검토를 끝까지 마치지 못했습니다."

# 미완료 사유 (종료 사유별). 그 밖의 미완료는 검증 미완료로 본다.
_INCOMPLETE_NOTICES = {
    ExecutionEndReason.RETRY_LIMIT_EXCEEDED: "결과 검토를 여러 번 다시 했지만 진단을 확정하지 못했습니다.",
    ExecutionEndReason.NO_PROGRESS: "다시 진단해도 결과가 바뀌지 않아 진단을 멈췄습니다.",
    ExecutionEndReason.REVISION_REQUIRED: "결과 검토에서 고쳐야 할 부분이 남아 진단을 확정하지 못했습니다.",
    ExecutionEndReason.COST_LIMIT_EXCEEDED: "진단 비용 한도에 도달해 진단을 끝까지 마치지 못했습니다.",
    ExecutionEndReason.QUESTION_LIMIT_EXCEEDED: "추가 확인이 필요한 정보가 남아 진단을 끝까지 마치지 못했습니다.",
}
_UNVERIFIED_NOTICE = "결과 검증을 마치지 못했습니다."
_NO_REGULATED_TOOL_NOTICE = "상품 정보에서 인증·허가 대상 분야를 찾지 못했습니다(확정 아님)."


class ResultPresenter:
    """진단 결과를 공개 진단서로 바꾼다. 상태가 없어 여러 스레드에서 같이 써도 된다."""

    def assessment(self, result: FinalAssessment) -> PublicAssessmentDto:
        """완료·미완료 진단 결과의 공개 진단서.

        Args:
            result: 진단 결과.

        Returns:
            PublicAssessmentDto: 결과 상태·분야 카드·할 일·안내를 담은 진단서.
        """
        decision = decide_result_status(result)
        completed = is_completed(result)
        return PublicAssessmentDto(
            status="completed" if completed else "incomplete",
            result_status=decision.status.value,
            summary=_summary(decision),
            tool_reviews=[_card(tool, result) for tool in tool_order()],
            required_actions=_actions(result),
            notices=_notices(result, decision, completed),
        )


def _tool_result(result: FinalAssessment, tool: ToolName) -> ToolResult | None:
    return next((item for item in result.tool_results if item.tool_name is tool), None)


def _card(tool: ToolName, result: FinalAssessment) -> PublicToolReviewDto:
    """분야 카드 하나. 선택되지 않은 분야는 SKIPPED.

    선택됐는데 실행 기록이 없으면 결과 상태 규칙과 같이 검토 미완료(INCOMPLETE)로 본다.
    """
    tool_result = _tool_result(result, tool)
    selected = tool_result.selected if tool_result is not None else tool in result.selected_tools
    if not selected:
        return PublicToolReviewDto(tool_name=tool.name, status="SKIPPED", message=_SKIPPED_MESSAGE)
    status = _CARD_STATUS.get(tool_result.status, "INCOMPLETE") if tool_result is not None else "INCOMPLETE"
    return PublicToolReviewDto(
        tool_name=tool.name,
        status=status,
        # 원인 예외 내용은 넣지 않는다 (내부 오류 문구가 화면에 나가지 않게)
        message=_INCOMPLETE_MESSAGE if status == "INCOMPLETE" else None,
        findings=[_finding(finding) for finding in result.findings if finding.tool_name is tool],
    )


def _finding(finding: RegulatoryFinding) -> PublicFindingDto:
    """판단 하나를 공개 형식으로. 내부 전용 값(is_mock 등)은 빼고, BE 칸 길이를 넘으면 자른다."""
    subject = _clip(finding.subject, SUBJECT_MAX)
    summary = finding.summary.strip() or subject
    return PublicFindingDto(
        subject=subject,
        determination=finding.determination,
        risk_level=finding.risk_level,
        summary=summary,
        rationale=finding.rationale.strip() or summary,
        legal_sources=[_source(source) for source in finding.legal_sources if source.source_name.strip()],
    )


def _source(source: LegalSource) -> PublicLegalSourceDto:
    return PublicLegalSourceDto(
        source_name=_clip(source.source_name, SOURCE_FIELD_MAX),
        law_name=_clip_optional(source.law_name, SOURCE_FIELD_MAX),
        article=_clip_optional(source.article, SOURCE_FIELD_MAX),
        quoted_text=source.quoted_text,
        source_url=source.source_url,
        effective_date=_clip_optional(source.effective_date, EFFECTIVE_DATE_MAX),
    )


def _actions(result: FinalAssessment) -> list[str]:
    """할 일을 분야 순서로 중복 없이 모은다. tool이 품목마다 사입·구매대행 문장을 이어서 내므로 그 순서를 지킨다."""
    actions: list[str] = []
    for tool in tool_order():
        tool_result = _tool_result(result, tool)
        if tool_result is not None and tool_result.selected:
            actions.extend(tool_result.required_actions)
    # 종합 단계에서 따로 더한 할 일도 빠지지 않게 뒤에 붙인다
    actions.extend(result.required_actions)
    return _unique(actions)


def _notices(result: FinalAssessment, decision: ResultDecision, completed: bool) -> list[str]:
    notices: list[str] = []
    if not completed:
        notices.append(_INCOMPLETE_NOTICES.get(result.termination_reason, _UNVERIFIED_NOTICE))
    if decision.reason is DecisionReason.NO_REGULATED_TOOL:
        notices.append(_NO_REGULATED_TOOL_NOTICE)
    # 질문으로 묻지 않고 끝난 부족 정보 (답변 대기로 끝나면 질문 콜백으로 나가서 여기 오지 않음)
    notices.extend(result.missing_information)
    notices.append(DISCLAIMER)
    return _unique(notices)


def _summary(decision: ResultDecision) -> str:
    fields = "·".join(FIELD_LABELS[tool] for tool in decision.tools)
    match decision.reason:
        case DecisionReason.CERTIFICATION_REQUIRED:
            return f"{fields} 분야에서 판매 전 인증·허가 확인이 필요할 수 있습니다. 판매 방식별 할 일을 확인해 주세요."
        case DecisionReason.TOOL_FAILED:
            return f"{fields} 분야 검토를 마치지 못해 재확인이 필요합니다."
        case DecisionReason.INSUFFICIENT_INFORMATION:
            return f"{fields} 분야는 판단할 정보가 부족해 재확인이 필요합니다."
        case DecisionReason.INCOMPLETE:
            return "진단을 끝까지 마치지 못해 재확인이 필요합니다."
        case DecisionReason.NO_REGULATED_TOOL:
            return "인증·허가 대상 분야를 찾지 못해 구매대행으로 판매할 수 있는 것으로 보입니다(확정 아님)."
        case DecisionReason.NO_REQUIREMENT:
            return "확인한 분야에서 판매 전 인증·허가 요건을 찾지 못했습니다(확정 아님)."
    raise ValueError(f"요약 문장이 없는 결정 단계입니다: {decision.reason}")


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _clip_optional(text: str | None, limit: int) -> str | None:
    """선택 칸. 비었거나 공백뿐이면 None."""
    if text is None or not text.strip():
        return None
    return _clip(text, limit)


def _unique(values) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))
