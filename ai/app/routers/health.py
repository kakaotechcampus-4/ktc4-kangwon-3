"""서버 상태 확인 라우터."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import load_settings, ConfigError
from app.prompts import load_prompt

router = APIRouter(tags=["Health"])

REQUIRED_PROMPTS = ("extraction", "selection", "verification", "image_triage")


@router.get("/health", summary="서버 생존 확인", description="프로세스가 살아 있는지만 알린다.")
async def health_check() -> dict:
    """프로세스가 살아 있는지만 알린다.

    Returns:
        dict: ``{"status": "UP"}``.
    """
    return {"status": "UP"}


@router.get("/health/ready", summary="서비스 준비 상태 확인", description="설정과 필수 프롬프트를 읽을 수 있는지 확인한다.")
async def readiness_check() -> JSONResponse:
    """설정과 필수 프롬프트를 읽을 수 있는지 확인한다.

    Returns:
        JSONResponse: 모두 읽히면 200 READY, 하나라도 실패하면 503 UNAVAILABLE과 실패 목록.
    """
    errors: list[str] = []

    try:
        load_settings()
    except ConfigError as e:
        errors.append(f"config: {e}")

    for name in REQUIRED_PROMPTS:
        try:
            load_prompt(name)
        except (ValueError, FileNotFoundError):
            errors.append(f"prompt: {name} 누락")
        except RuntimeError:
            # 패키지 prompt.md와 app/prompts 양쪽에 같은 프롬프트가 있음
            errors.append(f"prompt: {name} 중복")

    if errors:
        return JSONResponse(status_code=503, content={"status": "UNAVAILABLE", "errors": errors})
    return JSONResponse(status_code=200, content={"status": "READY"})
