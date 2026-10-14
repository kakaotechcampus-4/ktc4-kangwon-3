"""AI 서버 설정. 기존 ``from app.config import ...`` 경로를 그대로 쓰도록 하위 모듈을 다시 내보냄.

    - settings: 환경변수 → Settings
    - catalog: 채팅 모델 카탈로그(단가·추론 강도)
    - profiles: 에이전트별 모델 프로필
    - chat: 채팅 모델 생성
    - session: 진단 세션 실행 한도
"""

from .catalog import CHAT_MODELS, ChatModel, Price
from .chat import MAX_RETRIES, TIMEOUT_SECONDS, agent_profile, build_chat_model
from .profiles import AGENT_PROFILES, MODEL_PROFILES, ModelProfile
from .session import (MAX_INFLIGHT_SESSIONS, MAX_RUNNING_SESSIONS, SESSION_MAX_DURATION_SECONDS,
                      SESSION_RETENTION_SECONDS, SESSION_SWEEP_SECONDS)
from .settings import ENV_FILE, REQUIRED_ENV, ConfigError, Settings, get_settings, load_settings

__all__ = [
    "AGENT_PROFILES", "CHAT_MODELS", "ENV_FILE", "MAX_INFLIGHT_SESSIONS", "MAX_RETRIES", "MAX_RUNNING_SESSIONS",
    "MODEL_PROFILES", "REQUIRED_ENV", "SESSION_MAX_DURATION_SECONDS", "SESSION_RETENTION_SECONDS",
    "SESSION_SWEEP_SECONDS", "TIMEOUT_SECONDS", "ChatModel", "ConfigError", "ModelProfile", "Price", "Settings",
    "agent_profile", "build_chat_model", "get_settings", "load_settings",
]
