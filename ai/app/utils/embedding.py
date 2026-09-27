"""텍스트 → 벡터 임베딩 유틸리티.

엘리스 MLAPI의 OpenAI 호환 임베딩 엔드포인트를 사용한다.
API 키와 base_url은 LLM(config.py)과 공유한다.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"

DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"


class EmbeddingConfigError(RuntimeError):
    """임베딩 설정이 없거나 잘못되었다."""


@dataclass(frozen=True)
class EmbeddingSettings:
    """임베딩 모델 호출 설정. API 키, BASE_URL은 repr에 노출하지 않는다."""

    api_key: str = field(repr=False)
    base_url: str = field(repr=False)
    model: str = DEFAULT_EMBEDDING_MODEL

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise EmbeddingConfigError("OPENAI_API_KEY가 비어 있습니다.")
        if not self.base_url.strip():
            raise EmbeddingConfigError(
                "OPENAI_BASE_URL이 비어 있습니다. "
                ".env.example을 참고하세요."
            )


def load_embedding_settings() -> EmbeddingSettings:
    """ai/.env와 환경변수에서 임베딩 설정을 읽는다.

    Returns:
        EmbeddingSettings: 임베딩 모델 호출에 필요한 설정.

    Raises:
        EmbeddingConfigError: 필수 환경변수가 없을 때.
    """
    load_dotenv(dotenv_path=_ENV_FILE, override=False, encoding="utf-8-sig")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise EmbeddingConfigError(
            f"OPENAI_API_KEY가 없습니다. {_ENV_FILE}를 확인하세요."
        )

    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not base_url:
        raise EmbeddingConfigError(
            f"OPENAI_BASE_URL이 없습니다. {_ENV_FILE}를 확인하세요."
        )

    return EmbeddingSettings(
        api_key=api_key,
        base_url=base_url,
        model=os.environ.get("OPENAI_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL,
    )


def build_embedding_model(
    settings: EmbeddingSettings | None = None,
):
    """LangChain OpenAIEmbeddings 인스턴스를 생성한다.

    Args:
        settings: 임베딩 설정. None이면 환경변수에서 자동 로드한다.

    Returns:
        OpenAIEmbeddings: LangChain 임베딩 모델 인스턴스.

    Raises:
        EmbeddingConfigError: 필수 환경변수가 없을 때.
    """
    from langchain_openai import OpenAIEmbeddings

    resolved = settings or load_embedding_settings()
    return OpenAIEmbeddings(
        model=resolved.model,
        base_url=resolved.base_url,
        api_key=resolved.api_key,
    )


async def embed_text(text: str, settings: EmbeddingSettings | None = None) -> list[float]:
    """단일 텍스트를 벡터로 변환한다.

    Args:
        text: 임베딩할 텍스트.
        settings: 임베딩 설정. None이면 환경변수에서 자동 로드한다.

    Returns:
        list[float]: 1536차원 임베딩 벡터.
    """
    model = build_embedding_model(settings)
    return await model.aembed_query(text)


async def embed_texts(texts: list[str], settings: EmbeddingSettings | None = None) -> list[list[float]]:
    """여러 텍스트를 벡터로 일괄 변환한다.

    Args:
        texts: 임베딩할 텍스트 리스트.
        settings: 임베딩 설정. None이면 환경변수에서 자동 로드한다.

    Returns:
        list[list[float]]: 각 텍스트에 대한 1536차원 임베딩 벡터 리스트.
    """
    model = build_embedding_model(settings)
    return await model.aembed_documents(texts)
