"""채팅 모델 생성. 각 에이전트는 직접 ``ChatOpenAI``를 만들지 않고 ``build_chat_model``을 사용한다."""

from typing import TYPE_CHECKING

from ...config import ModelProfile, Settings, agent_profile, load_settings, tool_profile

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

TIMEOUT_SECONDS = 45.0
MAX_RETRIES = 1


def build_chat_model(profile: ModelProfile, settings: Settings | None = None) -> "BaseChatModel":
    """공통 설정과 모델 프로필로 LangChain ``ChatOpenAI`` 모델을 만든다.

    세 회사 모델 모두 게이트웨이의 OpenAI 호환 엔드포인트로 부르므로 ChatOpenAI 하나로 만듦.
    프로필에서 None인 옵션(temperature·reasoning_effort)은 보내지 않음.

    Args:
        profile: 모델 프로필 (agent_profile·tool_profile 결과).
        settings: 설정. None이면 load_settings()로 읽음.

    Returns:
        BaseChatModel: 스트리밍으로 부르는 채팅 모델.
    """

    # 설정 검사만 하는 코드가 SDK 없이도 import되도록 지연 import한다.
    from langchain_openai import ChatOpenAI

    resolved = settings or load_settings()
    options = {
        name: value
        for name, value in (("temperature", profile.temperature), ("reasoning_effort", profile.reasoning_effort))
        if value is not None
    }
    return ChatOpenAI(
        model=profile.model.id,
        base_url=resolved.base_url,
        api_key=resolved.api_key,
        **options,
        timeout=TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
        # ML API 게이트웨이는 스트리밍이 아닌 응답을 출력 2,000토큰에서 끊는다. 판매자 설명이 긴
        # 페이지는 추출 출력이 이를 넘어 JSON이 잘리고 파싱에 실패한다. 게이트웨이 안내대로 스트리밍으로
        # 받으면 이 한도에 걸리지 않는다(헤어드라이어 페이지 추출 출력 2,364토큰으로 확인).
        streaming=True,
        # 스트리밍에서도 응답에 토큰 사용량을 받아 usage.record()가 비용을 남길 수 있게 한다.
        stream_usage=True,
    )


def build_agent_model(name: str) -> "BaseChatModel":
    """에이전트 프로필로 채팅 모델을 만든다. 설정은 한 번만 읽음.

    Args:
        name: 에이전트 이름 (BaseAgent.component_name).

    Returns:
        BaseChatModel: 프로필대로 부르는 채팅 모델.

    Raises:
        ConfigError: 설정이 없거나 잘못됐거나, 프로필이 정해지지 않은 에이전트인 경우.
    """
    settings = load_settings()
    return build_chat_model(agent_profile(name, settings), settings)


def build_tool_model(name: str) -> "BaseChatModel":
    """Tool 프로필로 채팅 모델을 만든다. 설정은 한 번만 읽음.

    Args:
        name: Tool 이름 (ToolName 값).

    Returns:
        BaseChatModel: 프로필대로 부르는 채팅 모델.

    Raises:
        ConfigError: 설정이 없거나 잘못됐거나, 프로필이 정해지지 않은 Tool인 경우.
    """
    settings = load_settings()
    return build_chat_model(tool_profile(name, settings), settings)
