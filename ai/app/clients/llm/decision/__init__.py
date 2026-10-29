"""판단 API(/decisions) 클라이언트: 공통 베이스와 제공사별 형식 변환."""

from ....config import ConfigError, DecisionProfile, Settings, load_settings
from .base import DecisionClient
from .errors import DecisionResponseError
from .openai import OpenAIDecisionClient
from .typesafe import TypeSafeDecisionClient

# 카탈로그 vendor → 요청·응답 형식
_CLIENTS: dict[str, type[DecisionClient]] = {
    "typesafe": TypeSafeDecisionClient,
    "openai": OpenAIDecisionClient,
}


def build_decision_client(profile: DecisionProfile, settings: Settings | None = None) -> DecisionClient:
    """판단 프로필의 모델 회사에 맞는 판단 클라이언트를 만든다.

    Args:
        profile: 판단 프로필 (agent_decision_profile 결과).
        settings: 설정. None이면 load_settings()로 읽음.

    Returns:
        DecisionClient: 게이트웨이 주소·키를 넣은 판단 클라이언트.

    Raises:
        ConfigError: 설정이 없거나 잘못됐거나, 형식을 모르는 모델 회사인 경우.
    """
    client_class = _CLIENTS.get(profile.model.vendor)
    if client_class is None:
        raise ConfigError(f"판단 형식을 모르는 모델 회사입니다: {profile.model.id}")
    resolved = settings or load_settings()
    return client_class(resolved.base_url, resolved.api_key)


__all__ = [
    "DecisionClient", "DecisionResponseError", "OpenAIDecisionClient", "TypeSafeDecisionClient",
    "build_decision_client",
]
