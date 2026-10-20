"""개발용 진단 라우터 (#318). BE 없이 진단을 접수하고 상태 조회로 결과를 확인한다.

외부에 여는 경로는 이 라우터뿐이라 모든 요청에 개발용 API 키를 검사함(꺼져 있으면 404).
진단서 없이 접수해 BE로 콜백을 보내지 않음. 상품 ID는 서버가 dev- 접두어로 발급하고, 조회도 dev- 상품만.
"""

from fastapi import APIRouter, Depends, Request, status

from ..callbacks import AssessmentPresenter
from ..clients.base import mask_sensitive_params
from ..errors import AIResponseCode, AIServiceError
from ..schemas.agent import ExtractionInput
from ..schemas.request import DevDiagnosisRequest
from ..schemas.response import (
    AcceptedProduct,
    ApiResponse,
    DevDiagnosisAcceptedResponse,
    DevDiagnosisStatus,
    DevDiagnosisStatusResponse,
)
from ..schemas.schemas import FinalAssessment
from ..schemas.session import DiagnosisSession, SessionStatus
from ..sessions.errors import QueueFullError
from ..sessions.executor import SessionExecutor
from .dev_auth import require_dev_api_key
from .diagnose import get_session_executor

DEV_PRODUCT_PREFIX = "dev-"

router = APIRouter(prefix="/dev/diagnose", tags=["개발용 진단"], dependencies=[Depends(require_dev_api_key)])

_AUTH_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"model": ApiResponse, "description": "개발용 API 키가 없거나 틀림"},
    status.HTTP_404_NOT_FOUND: {"model": ApiResponse, "description": "개발용 진단이 꺼져 있거나 없는 상품"},
}


def get_assessment_presenter(request: Request) -> AssessmentPresenter:
    """lifespan에서 만든 진단서 변환기(콜백과 같은 것)를 꺼낸다. 테스트에서 의존성 교체용."""
    return request.app.state.assessment_presenter


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DevDiagnosisAcceptedResponse,
    responses={**_AUTH_RESPONSES, status.HTTP_429_TOO_MANY_REQUESTS: {"model": ApiResponse,
                                                                     "description": "개발용 진단 대기열 초과"}},
    summary="개발용 진단 접수",
    description="상품 하나를 진단으로 접수한다. 결과는 콜백 대신 상태 조회로 확인한다.",
)
async def submit_dev_diagnosis(
    req: DevDiagnosisRequest,
    executor: SessionExecutor = Depends(get_session_executor),
) -> DevDiagnosisAcceptedResponse:
    """개발용 진단을 접수하고 바로 202를 반환한다.

    Args:
        req: 상품 글·이미지.
        executor: 세션 실행기.

    Returns:
        202 접수 응답. 발급한 상품 ID·실행 ID.

    Raises:
        AIServiceError: 개발용 또는 전체 대기열이 차면 429.
    """
    item = ExtractionInput(
        product_id=DEV_PRODUCT_PREFIX, source_url=req.source_url, text_blocks=req.text_blocks,
        image_urls=req.image_urls,
    )
    try:
        session = executor.submit_dev(item)
    except QueueFullError as e:
        raise AIServiceError(response_code=AIResponseCode.QUEUE_FULL.value, retryable=True) from e
    return DevDiagnosisAcceptedResponse(
        code="OK",
        message="개발용 진단이 접수되었습니다.",
        data=AcceptedProduct(product_id=session.context.product_id, run_id=session.context.run_id),
    )


@router.get(
    "/{product_id}",
    response_model=DevDiagnosisStatusResponse,
    responses=_AUTH_RESPONSES,
    summary="개발용 진단 상태 조회",
    description="진행 단계와, 끝났으면 BE가 콜백으로 받을 공개 진단서·질문과 내부 결과를 반환한다.",
)
async def get_dev_diagnosis(
    product_id: str,
    executor: SessionExecutor = Depends(get_session_executor),
    presenter: AssessmentPresenter = Depends(get_assessment_presenter),
) -> DevDiagnosisStatusResponse:
    """개발용 진단 하나의 상태를 조회한다.

    Args:
        product_id: 접수 때 받은 dev- 상품 ID.
        executor: 세션 실행기.
        presenter: 공개 진단서·질문 변환기.

    Returns:
        상태 응답.

    Raises:
        AIServiceError: dev- 상품이 아니거나 없으면(보관 시간이 지나 지워진 경우 포함) 404.
    """
    session = executor.store.get(product_id) if product_id.startswith(DEV_PRODUCT_PREFIX) else None
    # 운영 상품 상태는 개발용 키로 보이지 않게 dev- 상품만
    if session is None:
        raise AIServiceError(response_code=AIResponseCode.NOT_FOUND.value)
    return DevDiagnosisStatusResponse(code="OK", message="개발용 진단 상태입니다.", data=_status(session, presenter))


def _status(session: DiagnosisSession, presenter: AssessmentPresenter) -> DevDiagnosisStatus:
    """세션을 상태 응답으로. 완료·답변 대기면 콜백과 같은 변환기로 공개 진단서·질문을 만듦."""
    assessment, question_round, questions, error = None, None, [], None
    if session.result is not None:
        try:
            if session.status is SessionStatus.COMPLETED:
                assessment = presenter.assessment(session.result)
            elif session.status is SessionStatus.AWAITING_INPUT:
                question_round, questions = presenter.questions(session.result)
        except Exception as exc:
            # 운영이라면 실패 콜백으로 끝나는 경우. 개발용은 원인을 보여 줌
            error = f"{type(exc).__name__}: {exc}"
    return DevDiagnosisStatus(
        product_id=session.context.product_id, run_id=session.context.run_id, status=session.status,
        stage=session.stage, error_code=session.error_code, retryable=session.retryable,
        accepted_at=session.accepted_at, updated_at=session.updated_at,
        assessment=assessment, question_round=question_round, questions=questions,
        presentation_error=error, result=_masked(session.result) if session.result is not None else None,
    )


def _masked(result: FinalAssessment) -> FinalAssessment:
    """내부 결과 속 외부 API 키를 가린 사본을 만든다. 세션의 원본은 그대로 둠.

    Args:
        result: 세션에 담긴 내부 결과.

    Returns:
        FinalAssessment: 키 값이 ``***``로 가려진 사본.
    """
    # 외부에 열린 경로라 나중에 붙을 Tool의 근거 URL 등에 키가 섞여도 노출 방지
    return FinalAssessment.model_validate_json(mask_sensitive_params(result.model_dump_json()))
