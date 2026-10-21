"""진단 라우터. 진단서 단위 접수(content), 답변 후 재진단(resume), URL 진단(미구현) 엔드포인트를 제공한다."""

from fastapi import APIRouter, Depends, Request, status

from ..errors import AIResponseCode, AIServiceError
from ..schemas.agent import ExtractionInput
from ..schemas.request import DiagnosisProductInput, DiagnosisRequest, ResumeRequest, UrlDiagnoseRequest
from ..schemas.response import (
    AcceptedProduct,
    ApiResponse,
    DiagnoseResponse,
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


def _to_extraction_input(product: DiagnosisProductInput) -> ExtractionInput:
    """API 입력을 추출 에이전트 입력으로 변환한다."""
    return ExtractionInput(
        product_id=product.product_id,
        source_url=product.source_url,
        text_blocks=product.text_blocks,
        image_urls=product.images_base64,
    )


@router.post(
    "/content",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DiagnosisAcceptedResponse,
    responses={
        status.HTTP_409_CONFLICT: {"model": ApiResponse, "description": "진행 중인 상품 포함. data.conflictProductIds"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ApiResponse, "description": "진단 대기열 초과"},
    },
    summary="진단서 단위 진단 접수",
    description="진단서 한 건의 상품들을 상품별 세션으로 접수한다. 결과는 상품별 콜백으로 전달 (#263).",
)
async def diagnose_by_content(
    req: DiagnosisRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> DiagnosisAcceptedResponse:
    """진단서의 상품들을 세션으로 접수하고 바로 202를 반환한다.

    하나라도 진행 중이면 전체를 거절함 (#263).

    Args:
        req: 진단서 ID와 상품 1~10개.
        manager: 세션 관리자.

    Returns:
        202 접수 응답.

    Raises:
        AIServiceError: 진행 중 상품이 섞이면 409(data.conflictProductIds), 대기열이 차면 429.
    """
    try:
        sessions = manager.submit(req.diagnosis_id, [_to_extraction_input(p) for p in req.products])
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
            diagnosis_id=req.diagnosis_id,
            products=[
                AcceptedProduct(product_id=session.context.product_id, run_id=session.context.run_id)
                for session in sessions
            ],
        ),
    )


@router.post(
    "/resume",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ResumeAcceptedResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ApiResponse, "description": "묻지 않은 질문의 답변 포함. data.questionKeys"},
        status.HTTP_404_NOT_FOUND: {"model": ApiResponse, "description": "세션 없음 (AI 재시작 등). BE는 실패로 처리"},
        status.HTTP_409_CONFLICT: {"model": ApiResponse, "description": "답변 대기 아님, 실행·회차·진단서 불일치"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ApiResponse,
                                               "description": "형식 오류, 또는 이번 회차 질문 중 답하지 않은 질문 있음"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ApiResponse, "description": "진단 대기열 초과"},
    },
    summary="답변 후 재진단 접수",
    description="답변 대기 상품에 이번 회차 답변을 더해 새 실행으로 접수한다. 결과는 새 runId의 콜백으로 전달 (#310).",
)
async def resume_diagnosis(
    req: ResumeRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> ResumeAcceptedResponse:
    """답변 대기 상품을 답변과 함께 재접수하고 바로 202를 반환한다.

    Args:
        req: 진단서·상품·질문으로 끝난 실행 ID, 질문 회차, 이번 회차 답변.
        manager: 세션 관리자.

    Returns:
        202 재진단 접수 응답. runId는 새 실행 ID.

    Raises:
        AIServiceError: 묻지 않은 질문 키면 400(data.questionKeys), 세션이 없으면 404,
            답변 대기가 아니거나 실행·회차·진단서가 다르면 409, 답하지 않은 질문이 있으면 422, 대기열이 차면 429.
    """
    try:
        session = manager.resume(
            diagnosis_id=req.diagnosis_id,
            product_id=req.product_id,
            run_id=req.run_id,
            question_round=req.question_round,
            answers={answer.question_key: answer.answer_text for answer in req.answers},
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


@router.post("/url", response_model=DiagnoseResponse, summary="URL 진단", description="상품 URL로 크롤링 후 규제 진단을 실행한다.")
async def diagnose_by_url(req: UrlDiagnoseRequest) -> DiagnoseResponse:
    """URL 입력으로 상품을 진단한다. 서버가 직접 크롤링한다.

    Args:
        req: 크롤링할 URL과 식별자를 담은 요청.

    Returns:
        진단 파이프라인 실행 결과.
    """
    # TODO: 크롤링 구현 후 파이프라인 연결
    raise AIServiceError(response_code=AIResponseCode.NOT_IMPLEMENTED.value)
