"""에이전트·Tool이 쓸 모델 프로필 고르기. 모델 생성은 clients.llm."""

from .profiles import MODEL_PROFILES, ModelProfile
from .errors import ConfigError
from .settings import Settings, load_settings


def agent_profile(name: str, settings: Settings | None = None) -> ModelProfile:
    """에이전트가 쓸 모델 프로필 (AGENT_PROFILES 기본값 또는 MODEL_PROFILE_OVERRIDES의 agent.이름).

    Args:
        name: 에이전트 이름 (BaseAgent.component_name. 예: "extraction").
        settings: 설정. None이면 load_settings()로 읽음.

    Returns:
        ModelProfile: 고른 프로필.

    Raises:
        ConfigError: AGENT_PROFILES에 없는 에이전트인 경우.
    """
    resolved = settings or load_settings()
    return _pick("에이전트", resolved.agent_profiles, name)


def tool_profile(name: str, settings: Settings | None = None) -> ModelProfile:
    """Tool이 쓸 모델 프로필 (TOOL_PROFILES 기본값 또는 MODEL_PROFILE_OVERRIDES의 tool.이름).

    Args:
        name: Tool 이름 (ToolName 값. 예: "electrical_safety").
        settings: 설정. None이면 load_settings()로 읽음.

    Returns:
        ModelProfile: 고른 프로필.

    Raises:
        ConfigError: TOOL_PROFILES에 없는 Tool인 경우.
    """
    resolved = settings or load_settings()
    return _pick("Tool", resolved.tool_profiles, name)


def _pick(kind: str, profiles: dict[str, str], name: str) -> ModelProfile:
    if name not in profiles:
        raise ConfigError(f"모델 프로필이 정해지지 않은 {kind}입니다: {name!r}")
    return MODEL_PROFILES[profiles[name]]
