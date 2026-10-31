"""텍스트 → 벡터 임베딩 유틸리티.

엘리스 MLAPI의 OpenAI 호환 임베딩 엔드포인트를 사용한다.
API 키·base_url·임베딩 모델 이름은 공통 설정(config.Settings)에서 가져온다.
"""

from ...config import Settings, get_settings
from .client import get_llm_client


def build_embedding_model(
    settings: Settings | None = None,
):
    """LangChain OpenAIEmbeddings 인스턴스를 생성한다. 동기 호출은 공유 LlmClient 연결을 씀.

    Args:
        settings: 공통 설정. None이면 get_settings()의 공용 설정을 쓴다.

    Returns:
        OpenAIEmbeddings: LangChain 임베딩 모델 인스턴스.

    Raises:
        ConfigError: 필수 환경변수가 없거나 값이 형식·허용 범위를 벗어난 경우.
    """
    from langchain_openai import OpenAIEmbeddings

    resolved = settings or get_settings()
    return OpenAIEmbeddings(
        model=resolved.embedding_model,
        base_url=resolved.base_url,
        api_key=resolved.api_key,
        # 비동기(aembed_*)는 LangChain 기본 연결 그대로 (앱에서 아직 안 씀)
        http_client=get_llm_client(resolved.base_url).http_client,
    )


async def embed_text(text: str, settings: Settings | None = None) -> list[float]:
    """단일 텍스트를 벡터로 변환한다.

    Args:
        text: 임베딩할 텍스트.
        settings: 공통 설정. None이면 get_settings()의 공용 설정을 쓴다.

    Returns:
        list[float]: 1536차원 임베딩 벡터.
    """
    model = build_embedding_model(settings)
    return await model.aembed_query(text)


async def embed_texts(texts: list[str], settings: Settings | None = None) -> list[list[float]]:
    """여러 텍스트를 벡터로 일괄 변환한다.

    Args:
        texts: 임베딩할 텍스트 리스트.
        settings: 공통 설정. None이면 get_settings()의 공용 설정을 쓴다.

    Returns:
        list[list[float]]: 각 텍스트에 대한 1536차원 임베딩 벡터 리스트.
    """
    model = build_embedding_model(settings)
    return await model.aembed_documents(texts)


def embed_text_sync(text: str, settings: Settings | None = None) -> list[float]:
    """embed_text의 동기판. 동기로 도는 Tool·적재 명령에서 쓴다.

    Args:
        text: 임베딩할 텍스트.
        settings: 공통 설정. None이면 get_settings()의 공용 설정을 쓴다.

    Returns:
        list[float]: 1536차원 임베딩 벡터.
    """
    return build_embedding_model(settings).embed_query(text)


def embed_texts_sync(texts: list[str], settings: Settings | None = None) -> list[list[float]]:
    """embed_texts의 동기판. 동기로 도는 Tool·적재 명령에서 쓴다.

    Args:
        texts: 임베딩할 텍스트 리스트.
        settings: 공통 설정. None이면 get_settings()의 공용 설정을 쓴다.

    Returns:
        list[list[float]]: 각 텍스트에 대한 1536차원 임베딩 벡터 리스트.
    """
    return build_embedding_model(settings).embed_documents(texts)
