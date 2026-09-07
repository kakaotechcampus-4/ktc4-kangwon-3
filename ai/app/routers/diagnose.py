"""진단 라우터. 입력 방식별 3종 엔드포인트를 제공한다."""

from fastapi import APIRouter, HTTPException

from ..schemas.request import (
    ImageDiagnoseRequest,
    TextDiagnoseRequest,
    UrlDiagnoseRequest,
)
from ..schemas.response import DiagnoseResponse

router = APIRouter(prefix="/diagnose", tags=["진단"])


@router.post("/text", response_model=DiagnoseResponse, summary="텍스트 진단", description="상품 텍스트로 규제 진단을 실행한다.")
async def diagnose_by_text(req: TextDiagnoseRequest) -> DiagnoseResponse:
    """텍스트 입력으로 상품을 진단한다.

    Args:
        req: 상품 텍스트 블록과 식별자를 담은 요청.

    Returns:
        진단 파이프라인 실행 결과.
    """
    # TODO: 파이프라인 연결 — ExtractionInput 변환 → pipeline.run()
    raise HTTPException(status_code=501, detail="텍스트 진단은 아직 구현되지 않았습니다.")


@router.post("/image", response_model=DiagnoseResponse, summary="이미지 진단", description="상품 이미지로 규제 진단을 실행한다.")
async def diagnose_by_image(req: ImageDiagnoseRequest) -> DiagnoseResponse:
    """이미지 입력으로 상품을 진단한다.

    Args:
        req: 이미지 URL/base64와 식별자를 담은 요청.

    Returns:
        진단 파이프라인 실행 결과.
    """
    # TODO: 파이프라인 연결 — ExtractionInput 변환 → pipeline.run()
    raise HTTPException(status_code=501, detail="이미지 진단은 아직 구현되지 않았습니다.")


@router.post("/url", response_model=DiagnoseResponse, summary="URL 진단", description="상품 URL로 크롤링 후 규제 진단을 실행한다.")
async def diagnose_by_url(req: UrlDiagnoseRequest) -> DiagnoseResponse:
    """URL 입력으로 상품을 진단한다. 서버가 직접 크롤링한다.

    Args:
        req: 크롤링할 URL과 식별자를 담은 요청.

    Returns:
        진단 파이프라인 실행 결과.
    """
    # TODO: 크롤링 구현 후 파이프라인 연결
    raise HTTPException(status_code=501, detail="URL 크롤링 진단은 아직 구현되지 않았습니다.")
