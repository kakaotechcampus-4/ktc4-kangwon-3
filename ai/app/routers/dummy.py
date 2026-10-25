"""더미 진단 라우터. /diagnose와 같은 요청·응답·콜백으로 시나리오 더미를 돌림 (BE·FE 연동 확인용).

BE는 실제 파이프라인 연결([콜백 5/5]) 전까지 이 경로를 쓰고, 연결 뒤 접두어만 /diagnose로 바꿈.
"""

from fastapi import APIRouter, Depends, Query, status

from ..domain.context import RunType
from ..dummy import DummyFlow, DummyResult, DummyScenario, mark_scenario, random_scenario
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

router = APIRouter(prefix="/dummy/diagnose", tags=["더미 진단"])


@router.post(
    "/content",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DiagnosisAcceptedResponse,
    responses=SUBMIT_RESPONSES,
    summary="진단서 단위 더미 진단 접수",
    description=(
        "/diagnose/content와 같은 요청으로 접수하고 시나리오대로 진행·질문·결과·실패 콜백을 보낸다. "
        "flow·result를 빼면 상품마다 무작위로 고름. 재진단은 /dummy/diagnose/resume으로."
    ),
)
async def dummy_diagnose_by_content(
    req: DiagnosisRequest,
    flow: DummyFlow | None = Query(None, description="질문·실패 흐름. 없으면 무작위"),
    result: DummyResult | None = Query(None, description="완료 결과 종류. 없으면 무작위"),
    manager: SessionManager = Depends(get_session_manager),
) -> DiagnosisAcceptedResponse:
    """진단서의 상품들을 더미 세션으로 접수하고 바로 202를 반환한다.

    Args:
        req: 진단서 ID와 상품 1~10개.
        flow: 모든 상품에 쓸 흐름. 없으면 상품마다 무작위.
        result: 모든 상품에 쓸 결과 종류. 없으면 상품마다 무작위.
        manager: 세션 관리자.

    Returns:
        202 접수 응답.

    Raises:
        AIServiceError: 진행 중 상품이 섞이면 409(data.conflictProductIds), 대기열이 차면 429.
    """
    inputs = []
    for product in req.products:
        picked = random_scenario()
        scenario = DummyScenario(flow=flow or picked.flow, result=result or picked.result)
        inputs.append(mark_scenario(to_extraction_input(product), scenario))
    return submit_diagnosis(manager, req.diagnosis_id, inputs, RunType.DUMMY)


@router.post(
    "/resume",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ResumeAcceptedResponse,
    responses=RESUME_RESPONSES,
    summary="더미 진단 답변 후 재진단 접수",
    description="/diagnose/resume과 같은 요청. /dummy/diagnose/content로 접수한 상품만 받고, 처음 고른 시나리오를 이어감.",
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
