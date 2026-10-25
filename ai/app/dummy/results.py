"""결과 종류별 더미 진단 결과. RC 보트 더미 결과를 바꿔 만듦."""

from ..routers._dummy import build_dummy_assessment
from ..schemas.callback import PublicQuestionDto
from ..schemas.schemas import (
    ExecutionEndReason,
    FinalAssessment,
    FinalVerificationStatus,
    OverallStatus,
    ToolName,
    ToolResult,
    ToolStatus,
    VerificationStatus,
)
from ..schemas.session import SessionAnswer
from .scenario import DummyResult

# 회차별 질문. 2회차는 새 키만
QUESTIONS: dict[int, list[PublicQuestionDto]] = {
    1: [
        PublicQuestionDto(
            question_key="battery_only", question_order=1, question_text="내장 배터리로만 동작하나요?",
            help_text="배터리 전용이면 안전인증 대상에서 빠질 수 있어요.",
        ),
        PublicQuestionDto(
            question_key="frequency_band", question_order=2, question_text="무선 주파수 대역이 어떻게 되나요?",
            help_text="상품 설명이나 본체 라벨의 GHz 표기를 알려 주세요.",
        ),
    ],
    2: [
        PublicQuestionDto(
            question_key="waterproof_rating", question_order=1, question_text="방수 등급(IPX)이 표기돼 있나요?",
        ),
    ],
}

# 대행 구매 가능 결과에서 건너뜀으로 바꾸는 분야
_ALLOWED_SKIPPED = {ToolName.RADIO, ToolName.ELECTRICAL, ToolName.CHILDREN}


def awaiting_result(product_id: str) -> FinalAssessment:
    """질문으로 끝난 실행의 더미 결과.

    Args:
        product_id: 상품 ID.

    Returns:
        FinalAssessment: 종료 사유 user_input_required, 검증 미완료.
    """
    return build_dummy_assessment(product_id).model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
    })


def final_result(product_id: str, kind: DummyResult, answers: list[SessionAnswer]) -> FinalAssessment:
    """결과 종류에 맞는 완료 결과. 받은 답변은 요약 끝에 붙임.

    Args:
        product_id: 상품 ID.
        kind: 결과 종류.
        answers: 지금까지 받은 답변.

    Returns:
        FinalAssessment: 더미 완료 결과.
    """
    result = _BUILDERS[kind](build_dummy_assessment(product_id))
    if answers:
        result = result.model_copy(update={"summary": f"{result.summary}\n\n{_answer_summary(answers)}"})
    return result


def _allowed(base: FinalAssessment) -> FinalAssessment:
    tool_results = [_skip(tool_result) if tool_result.tool_name in _ALLOWED_SKIPPED else tool_result
                    for tool_result in base.tool_results]
    return base.model_copy(update={
        "verification_status": FinalVerificationStatus.VERIFIED,
        "overall_status": OverallStatus.LIKELY_COMPLIANT,
        "summary": "(더미) 인증 대상 분야가 없어 구매대행으로 판매할 수 있는 예시 결과입니다.",
        "selected_tools": [tool_result.tool_name for tool_result in tool_results if tool_result.selected],
        "tool_results": tool_results,
        "findings": [finding for tool_result in tool_results for finding in tool_result.findings],
        "required_actions": ["전자상거래 상품정보 제공 고시 필수 표시사항 기재"],
        "missing_information": [],
        "verification": base.verification.model_copy(update={"status": VerificationStatus.APPROVED}),
    })


def _certification(base: FinalAssessment) -> FinalAssessment:
    return base


def _recheck(base: FinalAssessment) -> FinalAssessment:
    tool_results = [
        tool_result.model_copy(update={"status": ToolStatus.FAILED, "error": "더미 조회 실패"})
        if tool_result.tool_name is ToolName.CUSTOMS else tool_result
        for tool_result in base.tool_results
    ]
    return base.model_copy(update={
        "verification_status": FinalVerificationStatus.INCOMPLETE,
        "termination_reason": ExecutionEndReason.RETRY_LIMIT_EXCEEDED,
        "overall_status": OverallStatus.INSUFFICIENT_INFORMATION,
        "summary": "(더미) 일부 분야를 확인하지 못해 판매 전 재확인이 필요한 예시 결과입니다.",
        "tool_results": tool_results,
        "missing_information": ["관세 분야 조회에 실패해 세관장확인 요건을 확인하지 못했습니다.",
                                *base.missing_information],
    })


_BUILDERS = {
    DummyResult.ALLOWED: _allowed,
    DummyResult.CERTIFICATION: _certification,
    DummyResult.RECHECK: _recheck,
}


def _skip(tool_result: ToolResult) -> ToolResult:
    return tool_result.model_copy(update={
        "status": ToolStatus.SKIPPED, "selected": False, "selection_reason": "(더미) 해당 사항 없음",
        "result": None, "findings": [],
    })


def _answer_summary(answers: list[SessionAnswer]) -> str:
    texts = {
        question.question_key: question.question_text for questions in QUESTIONS.values() for question in questions
    }
    lines = [f"- {texts.get(answer.question_key, answer.question_key)} → {answer.answer_text}" for answer in answers]
    return "받은 답변:\n" + "\n".join(lines)
