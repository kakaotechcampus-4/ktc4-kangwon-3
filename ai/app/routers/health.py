"""서버 상태 확인 라우터."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import load_settings, ConfigError
from app.prompts import load_prompt

router = APIRouter(tags=["Health"])

REQUIRED_PROMPTS = ("extraction", "selection", "verification")


@router.get("/health", summary="서버 생존 확인")
async def health_check() -> dict:
    return {"status": "UP"}


@router.get("/health/ready", summary="서비스 준비 상태 확인")
async def readiness_check() -> JSONResponse:
    errors: list[str] = []

    try:
        load_settings()
    except ConfigError as e:
        errors.append(f"config: {e}")

    for name in REQUIRED_PROMPTS:
        try:
            load_prompt(name)
        except (ValueError, FileNotFoundError):
            errors.append(f"prompt: {name}.md 누락")

    if errors:
        return JSONResponse(status_code=503, content={"status": "UNAVAILABLE", "errors": errors})
    return JSONResponse(status_code=200, content={"status": "READY"})
