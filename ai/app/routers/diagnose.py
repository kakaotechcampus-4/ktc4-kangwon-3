"""진단 라우터. 진단서 단위 접수(content)와 답변 후 재진단(resume) 엔드포인트를 제공한다.

실제 파이프라인 연결 전까지 접수는 501, 재진단은 접수된 세션이 없어 404.
BE 연동은 같은 처리를 쓰는 더미 경로(/dummy/diagnose)로 함.
"""

from fastapi import APIRouter, Depends, Request, status

from ..domain.context import RunType
from ..domain.errors import AIResponseCode, AIServiceError
from ..schemas.agent import ExtractionInput
from ..schemas.request import DiagnosisProductInput, DiagnosisRequest, ResumeRequest
from ..schemas.response import (
    AcceptedProduct,
    ApiResponse,
    DiagnosisAccepted,
    DiagnosisAcceptedResponse,
    DiagnosisConflict,
    ResumeAccepted,
    ResumeAcceptedResponse,
    UnknownQuestionKeys,
)
from ..sessions.errors import (
    QueueFullError,
    ResumeConflictError,
    SessionConflictError,
    SessionNotFoundError,
    UnansweredQuestionError,
    UnknownQuestionKeyError,
)
from ..sessions.manager import SessionManager

router = APIRouter(prefix="/diagnose", tags=["진단"])


def get_session_manager(request: Request) -> SessionManager:
    """lifespan에서 만든 세션 관리자를 꺼낸다. 테스트에서 의존성 교체용."""
    return request.app.state.session_manager


def to_extraction_input(product: DiagnosisProductInput) -> ExtractionInput:
    """API 입력을 추출 에이전트 입력으로 변환한다."""
    return ExtractionInput(
        product_id=product.product_id,
        source_url=product.source_url,
        text_blocks=product.text_blocks,
        image_urls=product.image_urls,
    )


# 접수·재진단 경로의 오류 응답. 더미 경로(/dummy/diagnose)도 같이 씀
SUBMIT_RESPONSES = {
    status.HTTP_409_CONFLICT: {"model": ApiResponse, "description": "실행 중인 상품 포함. data.conflictProductIds"},
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": ApiResponse, "description": "진단 대기열 초과"},
}
RESUME_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {"model": ApiResponse, "description": "묻지 않은 질문의 답변 포함. data.questionKeys"},
    status.HTTP_404_NOT_FOUND: {"model": ApiResponse, "description": "세션 없음 (AI 재시작 등). BE는 실패로 처리"},
    status.HTTP_409_CONFLICT: {"model": ApiResponse, "description": "답변 대기 아님, 실행·회차·진단서 불일치"},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ApiResponse,
                                           "description": "형식 오류, 또는 이번 회차 질문 중 답하지 않은 질문 있음"},
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": ApiResponse, "description": "진단 대기열 초과"},
}
# 실제 파이프라인 연결 전 /diagnose/content 응답
_NOT_IMPLEMENTED_RESPONSES = {
    status.HTTP_501_NOT_IMPLEMENTED: {"model": ApiResponse, "description": "실제 파이프라인 연결 전. 더미 경로 사용"},
}


def submit_diagnosis(
    manager: SessionManager, diagnosis_id: str, inputs: list[ExtractionInput], run_type: RunType,
) -> DiagnosisAcceptedResponse:
    """상품들을 실행 종류로 접수하고 202 응답 본문을 만든다. 세션 예외는 응답 코드로 바꿈.

    Args:
        manager: 세션 관리자.
        diagnosis_id: BE 진단서 ID.
        inputs: 상품별 입력.
        run_type: 실행 종류.

    Returns:
        DiagnosisAcceptedResponse: 접수된 상품별 실행 ID.

    Raises:
        AIServiceError: 진행 중 상품이 섞이면 409(data.conflictProductIds), 대기열이 차면 429.
    """
    try:
        sessions = manager.submit(diagnosis_id, inputs, run_type=run_type)
    except SessionConflictError as e:
        raise AIServiceError(
            response_code=AIResponseCode.SESSION_CONFLICT.value,
            data=DiagnosisConflict(conflict_product_ids=e.product_ids),
        ) from e
    except QueueFullError as e:
        raise AIServiceError(response_code=AIResponseCode.QUEUE_FULL.value, retryable=True) from e

    return DiagnosisAcceptedResponse(
        code="OK",
        message="진단 요청이 접수되었습니다.",
        data=DiagnosisAccepted(
            diagnosis_id=diagnosis_id,
            products=[
                AcceptedProduct(product_id=session.context.product_id, run_id=session.context.run_id)
                for session in sessions
            ],
        ),
    )


def resume_session(manager: SessionManager, req: ResumeRequest, run_type: RunType) -> ResumeAcceptedResponse:
    """답변 대기 상품을 재접수하고 202 응답 본문을 만든다. 세션 예외는 응답 코드로 바꿈.

    Args:
        manager: 세션 관리자.
        req: 진단서·상품·질문으로 끝난 실행 ID, 질문 회차, 이번 회차 답변.
        run_type: 재진단 경로의 실행 종류. 다른 경로로 접수된 세션은 없음으로 봄.

    Returns:
        ResumeAcceptedResponse: 새 실행 ID.

    Raises:
        AIServiceError: 묻지 않은 질문 키면 400(data.questionKeys), 세션이 없거나 실행 종류가 다르면 404,
            답변 대기가 아니거나 실행·회차·진단서가 다르면 409, 답하지 않은 질문이 있으면 422, 대기열이 차면 429.
    """
    try:
        session = manager.resume(
            diagnosis_id=req.diagnosis_id,
            product_id=req.product_id,
            run_id=req.run_id,
            question_round=req.question_round,
            answers={answer.question_key: answer.answer_text for answer in req.answers},
            run_type=run_type,
        )
    except UnknownQuestionKeyError as e:
        raise AIServiceError(
            response_code=AIResponseCode.UNKNOWN_QUESTION_KEY.value,
            data=UnknownQuestionKeys(question_keys=e.question_keys),
        ) from e
    except UnansweredQuestionError as e:
        # BE 답변 제출도 전부 답해야 받아서 새 응답 코드 없이 형식 오류로
        raise AIServiceError(response_code=AIResponseCode.INVALID_REQUEST.value) from e
    except SessionNotFoundError as e:
        raise AIServiceError(response_code=AIResponseCode.SESSION_NOT_FOUND.value) from e
    except ResumeConflictError as e:
        raise AIServiceError(response_code=AIResponseCode.RESUME_CONFLICT.value) from e
    except QueueFullError as e:
        raise AIServiceError(response_code=AIResponseCode.QUEUE_FULL.value, retryable=True) from e

    return ResumeAcceptedResponse(
        code="OK",
        message="재진단 요청이 접수되었습니다.",
        data=ResumeAccepted(product_id=session.context.product_id, run_id=session.context.run_id),
    )


@router.post(
    "/content",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DiagnosisAcceptedResponse,
    responses={**SUBMIT_RESPONSES, **_NOT_IMPLEMENTED_RESPONSES},
    summary="진단서 단위 진단 접수",
    description=(
        "진단서 한 건의 상품들을 상품별 세션으로 접수한다. 결과는 상품별 콜백으로 전달 (#263). "
        "실제 파이프라인 연결 전까지 501."
    ),
)
async def diagnose_by_content(req: DiagnosisRequest) -> DiagnosisAcceptedResponse:
    """진단서의 상품들을 접수한다. 실제 파이프라인 연결 전까지 접수하지 않음.

    Args:
        req: 진단서 ID와 상품 1~10개. 형식은 검사함.

    Raises:
        AIServiceError: 항상 501.
    """
    raise AIServiceError(response_code=AIResponseCode.NOT_IMPLEMENTED.value)


@router.post(
    "/resume",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ResumeAcceptedResponse,
    responses=RESUME_RESPONSES,
    summary="답변 후 재진단 접수",
    description=(
        "답변 대기 상품에 이번 회차 답변을 더해 새 실행으로 접수한다. 결과는 새 runId의 콜백으로 전달 (#310). "
        "실제 파이프라인 연결 전에는 /diagnose로 접수한 세션이 없어 404."
    ),
)
async def resume_diagnosis(
    req: ResumeRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> ResumeAcceptedResponse:
    """답변 대기 상품을 답변과 함께 재접수하고 바로 202를 반환한다.

    실제 파이프라인 연결 전에는 접수(/diagnose/content)가 501이라 세션이 없어 항상 404.
    더미로 접수한 상품도 실행 종류가 달라 404.

    Args:
        req: 진단서·상품·질문으로 끝난 실행 ID, 질문 회차, 이번 회차 답변.
        manager: 세션 관리자.

    Returns:
        202 재진단 접수 응답. runId는 새 실행 ID.

    Raises:
        AIServiceError: 세션이 없거나 /diagnose로 접수한 상품이 아니면 404. 그 밖은 RESUME_RESPONSES와 같음.
    """
    return resume_session(manager, req, RunType.PRODUCTION)
