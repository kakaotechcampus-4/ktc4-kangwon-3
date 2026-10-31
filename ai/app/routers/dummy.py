"""더미 진단 라우터. /diagnose와 같은 요청·응답·콜백으로 케이스 더미를 돌림 (BE·FE 연동 확인용).

BE는 실제 파이프라인 연결([콜백 5/5]) 전까지 이 경로를 쓰고, 연결 뒤 접두어만 /diagnose로 바꿈.
"""

from fastapi import APIRouter, Depends, Query, status

from ..domain.context import RunType
from ..dummy import DummyCaseName, mark_case, random_case
from ..schemas.request import DiagnosisRequest, ResumeRequest
from ..schemas.response import DiagnosisAcceptedResponse, ResumeAcceptedResponse
from ..sessions.manager import SessionManager
from .diagnose import (
    RESUME_RESPONSES,
    SUBMIT_RESPONSES,
    get_session_manager,
    resume_session,
    submit_diagnosis,
    to_extraction_input,
)
from .internal_auth import INTERNAL_AUTH_RESPONSES, require_internal_token

router = APIRouter(prefix="/dummy/diagnose", tags=["더미 진단"], dependencies=[Depends(require_internal_token)],
                   responses=INTERNAL_AUTH_RESPONSES)


@router.post(
    "/content",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DiagnosisAcceptedResponse,
    responses=SUBMIT_RESPONSES,
    summary="진단서 단위 더미 진단 접수",
    description=(
        "/diagnose/content와 같은 요청으로 접수하고 상품 케이스대로 진행·질문·결과·실패 콜백을 보낸다. "
        "입력 내용과 상관없이 케이스의 고정 결과를 씀. case를 빼면 상품마다 무작위로 고름. "
        "재진단은 /dummy/diagnose/resume으로."
    ),
)
async def dummy_diagnose_by_content(
    req: DiagnosisRequest,
    case: DummyCaseName | None = Query(None, description="상품 케이스. 없으면 상품마다 무작위"),
    manager: SessionManager = Depends(get_session_manager),
) -> DiagnosisAcceptedResponse:
    """진단서의 상품들을 더미 세션으로 접수하고 바로 202를 반환한다.

    Args:
        req: 진단서 ID와 상품 1~10개.
        case: 모든 상품에 쓸 케이스. 없으면 상품마다 무작위.
        manager: 세션 관리자.

    Returns:
        202 접수 응답.

    Raises:
        AIServiceError: 진행 중 상품이 섞이면 409(data.conflictProductIds), 대기열이 차면 429.
    """
    inputs = [mark_case(to_extraction_input(product), case or random_case()) for product in req.products]
    return submit_diagnosis(manager, req.diagnosis_id, inputs, RunType.DUMMY)


@router.post(
    "/resume",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ResumeAcceptedResponse,
    responses=RESUME_RESPONSES,
    summary="더미 진단 답변 후 재진단 접수",
    description="/diagnose/resume과 같은 요청. /dummy/diagnose/content로 접수한 상품만 받고, 처음 고른 케이스를 이어감.",
)
async def dummy_resume_diagnosis(
    req: ResumeRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> ResumeAcceptedResponse:
    """더미 답변 대기 상품을 답변과 함께 재접수하고 바로 202를 반환한다.

    Args:
        req: 진단서·상품·질문으로 끝난 실행 ID, 질문 회차, 이번 회차 답변.
        manager: 세션 관리자.

    Returns:
        202 재진단 접수 응답. runId는 새 실행 ID.

    Raises:
        AIServiceError: /diagnose/resume과 같음. /diagnose로 접수한 상품은 404.
    """
    return resume_session(manager, req, RunType.DUMMY)
