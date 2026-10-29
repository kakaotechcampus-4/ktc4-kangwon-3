"""AI 서버 설정. 기존 ``from app.config import ...`` 경로를 그대로 쓰도록 하위 모듈을 다시 내보냄.

    - settings: 환경변수 → Settings
    - catalog: 채팅·판단 모델 카탈로그(단가·추론 강도)
    - profiles: 에이전트별 모델·판단 모델 프로필
    - chat: 에이전트·Tool별 모델·판단 모델 프로필 고르기 (모델 생성은 clients.llm)
    - session: 진단 세션 실행 한도
    - errors: 설정 예외(ConfigError)
"""

from .catalog import CHAT_MODELS, DECISION_MODELS, ChatModel, DecisionModel, Price
from .chat import agent_decision_profile, agent_profile, tool_profile
from .errors import ConfigError
from .profiles import (AGENT_DECISION_PROFILES, AGENT_PROFILES, DECISION_PROFILES, MODEL_PROFILES, TOOL_PROFILES,
                       DecisionProfile, ModelProfile)
from .session import (AWAITING_INPUT_RETENTION_SECONDS, MAX_DEV_INFLIGHT_SESSIONS, MAX_INFLIGHT_SESSIONS,
                      MAX_RUNNING_SESSIONS, SESSION_MAX_DURATION_SECONDS, SESSION_RETENTION_SECONDS,
                      SESSION_SWEEP_SECONDS)
from .settings import ENV_FILE, REQUIRED_ENV, Settings, get_settings, load_settings

__all__ = [
    "AGENT_DECISION_PROFILES", "AGENT_PROFILES", "AWAITING_INPUT_RETENTION_SECONDS", "CHAT_MODELS",
    "DECISION_MODELS", "DECISION_PROFILES", "ENV_FILE", "MAX_DEV_INFLIGHT_SESSIONS",
    "MAX_INFLIGHT_SESSIONS", "MAX_RUNNING_SESSIONS",
    "MODEL_PROFILES", "REQUIRED_ENV", "SESSION_MAX_DURATION_SECONDS", "SESSION_RETENTION_SECONDS",
    "SESSION_SWEEP_SECONDS", "TOOL_PROFILES", "ChatModel", "ConfigError", "DecisionModel", "DecisionProfile",
    "ModelProfile", "Price", "Settings",
    "agent_decision_profile", "agent_profile", "get_settings", "load_settings", "tool_profile",
]
