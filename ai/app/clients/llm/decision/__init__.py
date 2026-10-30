"""판단 API(/decisions) 클라이언트: 공통 베이스와 제공사별 형식 변환, 공유 연결."""

from threading import Lock

from ....config import ConfigError, DecisionProfile, Settings, load_settings
from .base import DecisionClient, check_request, questions_fingerprint
from .errors import DecisionRequestError, DecisionResponseError
from .openai import OpenAIDecisionClient
from .typesafe import TypeSafeDecisionClient

# 카탈로그 vendor → 요청·응답 형식
_CLIENTS: dict[str, type[DecisionClient]] = {
    "typesafe": TypeSafeDecisionClient,
    "openai": OpenAIDecisionClient,
}

# (vendor, base_url) → 공유 클라이언트. 에이전트를 자주 새로 만들어도 연결은 형식마다 하나
_shared: dict[tuple[str, str], DecisionClient] = {}
_lock = Lock()


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


def get_decision_client(profile: DecisionProfile) -> DecisionClient:
    """판단 프로필의 모델 회사 형식 공유 클라이언트. 없으면 만든다. 여러 스레드가 같이 불러도 하나만 만듦.

    Args:
        profile: 판단 프로필.

    Returns:
        DecisionClient: 공유 클라이언트.

    Raises:
        ConfigError: 설정이 없거나 잘못됐거나, 형식을 모르는 모델 회사인 경우.
    """
    settings = load_settings()
    key = (profile.model.vendor, settings.base_url)
    with _lock:
        if key not in _shared:
            _shared[key] = build_decision_client(profile, settings)
        return _shared[key]


def close_decision_clients() -> None:
    """공유 클라이언트를 모두 닫고 비운다. 서버 종료 때 부름 (다시 부르면 새로 만듦)."""
    with _lock:
        for client in _shared.values():
            client.close()
        _shared.clear()


__all__ = [
    "DecisionClient", "DecisionRequestError", "DecisionResponseError", "OpenAIDecisionClient",
    "TypeSafeDecisionClient", "build_decision_client", "check_request", "close_decision_clients",
    "get_decision_client", "questions_fingerprint",
]
