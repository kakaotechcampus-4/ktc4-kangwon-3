"""서버 상태 확인 라우터."""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=dict, summary="서버 상태 확인", description="서버 생존 여부를 반환한다.")
async def health_check() -> dict:
    """서버 생존 여부를 반환한다.

    Returns:
        {"status": "UP"} — 서버 정상 동작 중.
    """
    return {"status": "UP"}
