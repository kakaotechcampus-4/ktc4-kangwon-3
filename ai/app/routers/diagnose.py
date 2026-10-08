"""진단 라우터. 진단서 단위 접수(content)와 URL 진단(미구현) 엔드포인트를 제공한다."""

from fastapi import APIRouter, Depends, Request, status

from ..errors import AIResponseCode, AIServiceError
from ..schemas.agent import ExtractionInput
from ..schemas.request import DiagnosisProductInput, DiagnosisRequest, UrlDiagnoseRequest
from ..schemas.response import (
    ApiResponse,
    DiagnoseResponse,
    DiagnosisAccepted,
    DiagnosisAcceptedResponse,
    DiagnosisConflict,
)
from ..sessions.executor import QueueFullError, SessionExecutor
from ..sessions.store import SessionConflictError

router = APIRouter(prefix="/diagnose", tags=["진단"])


def get_session_executor(request: Request) -> SessionExecutor:
    """lifespan에서 만든 세션 실행기를 꺼낸다. 테스트에서 의존성 교체용."""
    return request.app.state.session_executor


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
    executor: SessionExecutor = Depends(get_session_executor),
) -> DiagnosisAcceptedResponse:
    """진단서의 상품들을 세션으로 접수하고 바로 202를 반환한다.

    하나라도 진행 중이면 전체를 거절함 (#263).

    Args:
        req: 진단서 ID와 상품 1~10개.
        executor: 세션 실행기.

    Returns:
        202 접수 응답.

    Raises:
        AIServiceError: 진행 중 상품이 섞이면 409(data.conflictProductIds), 대기열이 차면 429.
    """
    try:
        sessions = executor.submit(req.diagnosis_id, [_to_extraction_input(p) for p in req.products])
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
            accepted_product_ids=[session.context.product_id for session in sessions],
        ),
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
