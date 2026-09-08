"""ML API 연결 설정을 한곳에서 관리한다.

각 에이전트는 직접 ``ChatOpenAI``를 만들지 않고 ``build_chat_model``을 사용한다.
API 키는 저장소에 커밋하지 않고 ``ai/.env`` 또는 환경변수로 주입한다.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


# 실행 위치와 관계없이 이 프로젝트의 ai/.env만 읽는다.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

DEFAULT_MODEL = "openai/gpt-4.1-mini"

# 팀 공용 크레딧으로 의도하지 않은 모델을 호출하지 않도록 제한한다.
ALLOWED_MODELS = frozenset({DEFAULT_MODEL})

TIMEOUT_SECONDS = 45.0
MAX_RETRIES = 1


class ConfigError(RuntimeError):
    """ML API 연결 설정이 없거나 허용 범위를 벗어났다."""


@dataclass(frozen=True)
class Settings:
    """모델 호출 설정. API 키, BASE_URL은 repr에 노출하지 않는다."""

    api_key: str = field(repr=False)
    base_url: str = field(repr=False)
    model: str = DEFAULT_MODEL

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ConfigError("OPENAI_API_KEY가 비어 있습니다.")
        if not self.base_url.startswith("https://") or not self.base_url.rstrip("/").endswith("/v1"):
            # 팀별 엔드포인트 식별자가 오류 로그에 노출되지 않게 실제 값은 출력하지 않는다.
            raise ConfigError("채팅 Base URL은 /v1로 끝나는 HTTPS 주소여야 합니다.")
        if self.model not in ALLOWED_MODELS:
            allowed = ", ".join(sorted(ALLOWED_MODELS))
            raise ConfigError(f"허용되지 않은 모델입니다: {self.model!r} (허용: {allowed})")


def load_settings() -> Settings:
    """ai/.env와 환경변수에서 설정을 읽는다. 환경변수가 .env보다 우선한다."""

    load_dotenv(dotenv_path=ENV_FILE, override=False, encoding="utf-8-sig")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ConfigError(
            f"OPENAI_API_KEY가 없습니다. {ENV_FILE}를 만들고 키를 넣으세요 "
            "(.env.example 참고)."
        )

    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not base_url:
        raise ConfigError(
            f"OPENAI_BASE_URL이 없습니다. {ENV_FILE}에 주소를 설정하세요 "
            "(.env.example 참고)."
        )

    return Settings(
        api_key=api_key,
        base_url=base_url,
        model=os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL,
    )


def build_chat_model(settings: Settings | None = None) -> "BaseChatModel":
    """공통 설정으로 LangChain ``ChatOpenAI`` 모델을 만든다."""

    # 설정 검사만 하는 코드가 SDK 없이도 import되도록 지연 import한다.
    from langchain_openai import ChatOpenAI

    resolved = settings or load_settings()
    return ChatOpenAI(
        model=resolved.model,
        base_url=resolved.base_url,
        api_key=resolved.api_key,
        temperature=0,
        timeout=TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )
