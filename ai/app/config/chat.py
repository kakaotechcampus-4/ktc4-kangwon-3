"""채팅 모델 생성. 각 에이전트는 직접 ``ChatOpenAI``를 만들지 않고 ``build_chat_model``을 사용한다."""

from typing import TYPE_CHECKING

from .profiles import MODEL_PROFILES, ModelProfile
from .settings import ConfigError, Settings, load_settings

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

TIMEOUT_SECONDS = 45.0
MAX_RETRIES = 1


def agent_profile(agent: str, settings: Settings | None = None) -> ModelProfile:
    """에이전트가 쓸 모델 프로필을 돌려준다.

    Args:
        agent: 에이전트 이름 (AGENT_PROFILES의 키. 예: "extraction").
        settings: 설정. None이면 load_settings()로 읽음.

    Returns:
        ModelProfile: 기본값 또는 {에이전트}_MODEL_PROFILE로 고른 프로필.

    Raises:
        ConfigError: AGENT_PROFILES에 없는 에이전트인 경우.
    """
    resolved = settings or load_settings()
    if agent not in resolved.agent_profiles:
        raise ConfigError(f"모델 프로필이 정해지지 않은 에이전트입니다: {agent!r}")
    return MODEL_PROFILES[resolved.agent_profiles[agent]]


def build_chat_model(
    settings: Settings | None = None,
    *,
    temperature: float = 0,
) -> "BaseChatModel":
    """공통 설정으로 LangChain ``ChatOpenAI`` 모델을 만든다."""

    # 설정 검사만 하는 코드가 SDK 없이도 import되도록 지연 import한다.
    from langchain_openai import ChatOpenAI

    resolved = settings or load_settings()
    return ChatOpenAI(
        model=resolved.model,
        base_url=resolved.base_url,
        api_key=resolved.api_key,
        temperature=temperature,
        timeout=TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
        # ML API 게이트웨이는 스트리밍이 아닌 응답을 출력 2,000토큰에서 끊는다. 판매자 설명이 긴
        # 페이지는 추출 출력이 이를 넘어 JSON이 잘리고 파싱에 실패한다. 게이트웨이 안내대로 스트리밍으로
        # 받으면 이 한도에 걸리지 않는다(헤어드라이어 페이지 추출 출력 2,364토큰으로 확인).
        streaming=True,
        # 스트리밍에서도 응답에 토큰 사용량을 받아 usage.record()가 비용을 남길 수 있게 한다.
        stream_usage=True,
    )
