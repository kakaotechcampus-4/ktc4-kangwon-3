"""진단 결과(FinalAssessment)를 BE에 보낼 공개 진단서(PublicAssessmentDto)로 바꾼다.

콜백 이벤트 생성기가 받는 AssessmentPresenter 형식(assessment(result))을 그대로 따른다. 서버 조립에서 더미 변환기 대신 끼운다.
- 결과 상태: status.decide_result_status
- 분야 카드: 6개 분야를 모두 보냄(선택 안 된 분야는 SKIPPED). 판단은 그대로 옮기고 BE 칸 길이를 넘으면 자른다.
- 할 일: 계약상 진단서 한 목록. 분야 순서로 모으고, 품목·판매 방식은 문장 앞 라벨로 구분된다.
- 안내: 미완료 사유, 지원 분야 밖 신호, 구매대행 가능일 때 확인 범위, 질문으로 묻지 않은 부족 정보, 고정 안내.
- 결과 검토에서 막혀 확정 못 함으로 끝나면: 배너 요약에 재확인할 분야를, 그 분야 카드 message에 검토가 짚은 판단 제목을
  적는다(critical 지적만, 지적 원문은 내보내지 않음). 결과 상태와 안내의 종료 사유는 그대로.
"""

import re

from ..schemas.callback import (
    PublicAssessmentDto, PublicFindingDto, PublicLegalSourceDto, PublicToolReviewDto,
)
from ..schemas.schemas import (
    ExecutionEndReason, FinalAssessment, LegalSource, RegulatoryFinding, ToolName, ToolResult, ToolStatus,
)
from .status import (
    ACTION_DETERMINATIONS, DecisionReason, ResultDecision, ResultStatus, decide_result_status, is_completed,
    tool_order,
)

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

# 통관 결정사례 출처 이름 (tools/customs/tool.py의 _CASE_SOURCE와 같음)
_CASE_SOURCE = "관세청 품목분류 결정사례(CLIP)"
# 결정사례 출처 조문 "결정사례 … (HS 8414.59-9000, …)"의 HS 부분
_CASE_HS = re.compile(r"\(HS ([^)]+)\)$")

# 지원 분야 밖 신호 → (상품 종류, 확인하지 않는 법령)
_OUT_OF_SCOPE_LABELS = {
    "chemical_product": ("생활화학제품", "화학제품안전법"),
    "weapon_like": ("총포·도검류", "총포·도검·화약류 등의 안전관리에 관한 법률"),
    "plant_material": ("식물성 소재 제품", "식물방역법(수입 검역)"),
}
# 구매대행 가능일 때 확인한 범위 안내
_SCOPE_NOTICE = ("이 서비스는 통관, 전파, 식품·의약품, 전기용품, 어린이제품, 표시·광고 분야만 확인합니다. "
                 "생활용품 안전관리, 가스·소방용품 등 그 밖의 법령은 확인하지 않았습니다.")
_LABEL_AD_NOTE = " 다만 표시·광고 문구는 확인이 필요합니다."
# '요건 없음'으로 끝난 요약의 둘째 문장. "찾지 못했습니다(확정 아님)"처럼 말투로 흐리지 않고, 결과가 기대는 조건(입력한
# 상품 정보로 확인한 범위)과 확인하지 않은 범위를 따로 적는다 (11/11 실 사이트 의류: 초록 배너인데 설명이 불확실하게 읽힘).
# 첫 문장은 "없습니다"로 단정하지 않고 "나오지 않았습니다"로 쓴다. 통관의 '요건 없음'은 HS 후보 기준 조회 결과라
# HS가 틀리면 요건이 있을 수 있다 (#834 리뷰)
_UNCHECKED_LAWS = "이 서비스가 확인하지 않는 법령은 따로 확인이 필요합니다."
# 확정 못 함(결과 검토에서 막힘)일 때 재확인할 위치를 알리는 분야 이름. FE 카드 이름(TOOL_NAME_LABELS)과 같게 씀
_CARD_LABELS = {
    ToolName.CUSTOMS: "통관",
    ToolName.RADIO: "전파",
    ToolName.FOOD_DRUG: "식품·의약품",
    ToolName.ELECTRICAL: "전기 안전",
    ToolName.CHILDREN: "어린이 제품",
    ToolName.LABEL_AD: "표시·광고",
}


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
        recheck = _recheck_targets(result)
        return PublicAssessmentDto(
            status="completed" if completed else "incomplete",
            result_status=decision.status.value,
            summary=_recheck_summary(recheck) if recheck else _summary(decision, result),
            tool_reviews=[_card(tool, result, recheck.get(tool, [])) for tool in tool_order()],
            required_actions=_actions(result),
            notices=_notices(result, decision, completed),
        )


def _tool_result(result: FinalAssessment, tool: ToolName) -> ToolResult | None:
    return next((item for item in result.tool_results if item.tool_name is tool), None)


def _card(tool: ToolName, result: FinalAssessment, recheck: list[str] = ()) -> PublicToolReviewDto:
    """분야 카드 하나. 선택되지 않은 분야는 SKIPPED.

    선택됐는데 실행 기록이 없으면 결과 상태 규칙과 같이 검토 미완료(INCOMPLETE)로 본다.
    검토를 마친 카드에 결과 검토가 짚은 판단(recheck: 판단 제목)이 있으면 그 항목을 확인하라고 적는다.
    실행 미완료 카드는 기존 문구를 그대로 둔다.
    """
    tool_result = _tool_result(result, tool)
    selected = tool_result.selected if tool_result is not None else tool in result.selected_tools
    if not selected:
        return PublicToolReviewDto(tool_name=tool.name, status="SKIPPED", message=_SKIPPED_MESSAGE)
    status = _CARD_STATUS.get(tool_result.status, "INCOMPLETE") if tool_result is not None else "INCOMPLETE"
    if status == "INCOMPLETE":
        # 원인 예외 내용은 넣지 않는다 (내부 오류 문구가 화면에 나가지 않게)
        message = _INCOMPLETE_MESSAGE
    elif recheck:
        items = ", ".join(f"‘{subject}’" for subject in recheck)
        message = f"이 카드의 {items} 항목은 이번 진단에서 결론을 내리지 못했습니다. 아래 판단 근거가 판매할 상품에도 적용되는지 확인해 주세요."
    else:
        message = None
    return PublicToolReviewDto(
        tool_name=tool.name,
        status=status,
        message=message,
        findings=[_finding(finding) for finding in result.findings if finding.tool_name is tool],
    )


def _recheck_targets(result: FinalAssessment) -> dict[ToolName, list[str]]:
    """결과 검토에서 막혀 확정 못 함으로 끝났을 때, critical 지적이 가리킨 판단의 제목을 분야별로 모은다.

    검증 지적 원문은 모델이 쓴 글이라 내보내지 않고, 이미 카드에 공개하는 판단 제목만 쓴다.
    warning은 막지 않았으므로 빼고, 진단 결과에 없는 판단 ID는 건너뛴다. 종료 사유가 다르면 빈 dict.

    Args:
        result: 진단 결과.

    Returns:
        dict[ToolName, list[str]]: 분야 순서대로 분야 → 판단 제목(중복 없음). 연결할 판단이 없으면 빈 dict.
    """
    if result.termination_reason is not ExecutionEndReason.REVISION_REQUIRED:
        return {}
    by_id = {finding.finding_id: finding for finding in result.findings}
    targets: dict[ToolName, list[str]] = {}
    for issue in result.verification.issues:
        if issue.severity != "critical":
            continue
        for finding_id in issue.related_finding_ids:
            finding = by_id.get(finding_id)
            if finding is None:
                continue
            subjects = targets.setdefault(finding.tool_name, [])
            subject = _clip(finding.subject, SUBJECT_MAX)
            if subject not in subjects:
                subjects.append(subject)
    return {tool: targets[tool] for tool in tool_order() if tool in targets}


def _recheck_summary(recheck: dict[ToolName, list[str]]) -> str:
    """확정 못 함일 때 배너 요약. 재확인할 분야만 알린다.

    인증 후보 판단 자체가 지적받은 경우도 있어, 판단만 보고 낸 결론(인증 필요·요건 없음 등)은 되살리지 않는다.
    """
    labels = ", ".join(_CARD_LABELS[tool] for tool in recheck)
    return f"{labels} 분야에 재확인이 필요한 항목이 있습니다. 아래 해당 카드를 확인해 주세요."


def _finding(finding: RegulatoryFinding) -> PublicFindingDto:
    """판단 하나를 공개 형식으로. 내부 전용 값(is_mock 등)은 빼고, BE 칸 길이를 넘으면 자른다."""
    subject = _clip(finding.subject, SUBJECT_MAX)
    summary = finding.summary.strip() or subject
    return PublicFindingDto(
        subject=subject,
        determination=finding.determination,
        risk_level=finding.risk_level,
        summary=summary,
        rationale=_rationale(finding) or summary,
        legal_sources=[_source(source) for source in finding.legal_sources if source.source_name.strip()],
    )


def _rationale(finding: RegulatoryFinding) -> str:
    """판단 근거. 통관 근거가 결정사례마다 한 줄씩이면 대표 줄과 사례 요약 두 줄로 줄인다 (#709).

    통관 Tool은 고른 결정사례 순서대로 사례별 이유를 줄로 잇고 같은 순서로 결정사례 출처를 붙인다.
    사례별 이유가 상품 설명을 되풀이해 화면에서 중복처럼 보여, 사례 내용은 출처에 맡긴다.

    Args:
        finding: 판단 하나.

    Returns:
        str: 화면에 보낼 근거. 비면 빈 문자열.
    """
    rationale = finding.rationale.strip()
    if finding.tool_name is not ToolName.CUSTOMS:
        return rationale
    lines = [line.strip() for line in rationale.splitlines() if line.strip()]
    cases = [source for source in finding.legal_sources if source.source_name == _CASE_SOURCE]
    # 줄과 사례 출처 수가 다르면 짝을 믿을 수 없어 그대로 둠
    if len(lines) < 2 or len(lines) != len(cases):
        return rationale
    codes = list(dict.fromkeys(
        code for source in cases if (match := _CASE_HS.search(source.article or ""))
        for code in match.group(1).split(", ")
    ))
    hs = f" · HS {', '.join(codes)}" if codes else ""
    return f"판단: {lines[0]}\n참고 사례: {len(cases)}건{hs} · 아래 '근거'에서 확인"


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
    for signal in decision.signals:
        kind, law = _OUT_OF_SCOPE_LABELS[signal]
        notices.append(f"{kind}일 수 있어 {law} 대상인지 따로 확인해야 합니다. 이 서비스는 이 법령을 확인하지 않습니다.")
    if decision.status is ResultStatus.PURCHASING_AGENT_ALLOWED:
        notices.append(_SCOPE_NOTICE)
    # 질문으로 묻지 않고 끝난 부족 정보 (답변 대기로 끝나면 질문 콜백으로 나가서 여기 오지 않음)
    notices.extend(result.missing_information)
    notices.append(DISCLAIMER)
    return _unique(notices)


def _summary(decision: ResultDecision, result: FinalAssessment) -> str:
    text = _base_summary(decision)
    # 표시·광고는 결과 상태에서 빠지므로, 구매대행 가능인데 문구 판단이 있으면 같이 알린다
    if decision.status is ResultStatus.PURCHASING_AGENT_ALLOWED and _has_label_ad_action(result):
        text += _LABEL_AD_NOTE
    return text


def _base_summary(decision: ResultDecision) -> str:
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
        case DecisionReason.OUT_OF_SCOPE:
            kinds = ", ".join(_OUT_OF_SCOPE_LABELS[signal][0] for signal in decision.signals)
            return f"이 상품은 {kinds}일 수 있어, 이 서비스가 확인하지 않는 법령의 규제 대상인지 재확인이 필요합니다."
        case DecisionReason.NO_REGULATED_TOOL:
            return f"입력하신 상품 정보로 확인한 범위에서는 인증이나 허가가 필요한 분야가 나오지 않았습니다. {_UNCHECKED_LAWS}"
        case DecisionReason.NO_REQUIREMENT:
            return f"입력하신 상품 정보로 확인한 범위에서는 {fields}에서 판매 전에 갖출 인증이나 허가가 나오지 않았습니다. {_UNCHECKED_LAWS}"
    raise ValueError(f"요약 문장이 없는 결정 단계입니다: {decision.reason}")


def _has_label_ad_action(result: FinalAssessment) -> bool:
    return any(finding.tool_name is ToolName.LABEL_AD and finding.determination in ACTION_DETERMINATIONS
               for finding in result.findings)


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
