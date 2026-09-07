"""더미 진단 라우터. BE 연동 테스트용으로 고정 결과를 반환한다."""

from fastapi import APIRouter

from ..schemas.request import (
    ImageDiagnoseRequest,
    TextDiagnoseRequest,
    UrlDiagnoseRequest,
)
from ..schemas.response import DiagnoseResponse, ok_diagnose
from ._dummy import build_dummy_assessment

router = APIRouter(prefix="/dummy/diagnose", tags=["더미 진단"])


@router.post("/text", response_model=DiagnoseResponse, summary="텍스트 더미 진단", description="요청 스키마만 검증하고 RC 보트 고정 결과를 반환한다.")
async def dummy_diagnose_by_text(req: TextDiagnoseRequest) -> DiagnoseResponse:
    """텍스트 입력 더미 진단.

    Returns:
        RC 보트 기반 더미 FinalAssessment.
    """
    return ok_diagnose(build_dummy_assessment(req.product_id))


@router.post("/image", response_model=DiagnoseResponse, summary="이미지 더미 진단", description="요청 스키마만 검증하고 RC 보트 고정 결과를 반환한다.")
async def dummy_diagnose_by_image(req: ImageDiagnoseRequest) -> DiagnoseResponse:
    """이미지 입력 더미 진단.

    Returns:
        RC 보트 기반 더미 FinalAssessment.
    """
    return ok_diagnose(build_dummy_assessment(req.product_id))


@router.post("/url", response_model=DiagnoseResponse, summary="URL 더미 진단", description="요청 스키마만 검증하고 RC 보트 고정 결과를 반환한다.")
async def dummy_diagnose_by_url(req: UrlDiagnoseRequest) -> DiagnoseResponse:
    """URL 입력 더미 진단.

    Returns:
        RC 보트 기반 더미 FinalAssessment.
    """
    return ok_diagnose(build_dummy_assessment(req.product_id))
