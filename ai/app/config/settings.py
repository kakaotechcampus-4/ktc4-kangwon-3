"""환경변수·ai/.env를 읽어 검증한 AI 서버 설정 (ML API · DB · 외부 API 키).

API 키는 저장소에 커밋하지 않고 ``ai/.env`` 또는 환경변수로 주입한다.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from .profiles import AGENT_PROFILES, MODEL_PROFILES, TOOL_PROFILES

# 실행 위치와 관계없이 이 프로젝트의 ai/.env만 읽는다.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# 서버 기동을 위한 필수 환경변수 목록
REQUIRED_ENV = {
    "OPENAI_API_KEY": "api_key",
    "OPENAI_BASE_URL": "base_url",
    "OPENAI_EMBEDDING_MODEL": "embedding_model",
    "DATA_GO_KR_KEY": "data_go_kr_key",
    "KEY_SAFETYKOREA": "safetykorea_key",
    "LAW_GO_KR_OC": "law_oc",
}


class ConfigError(RuntimeError):
    """AI 서버 설정이 없거나 허용 범위를 벗어났다."""


# 프로필 표 종류. 종류마다 표와 환경변수 접두어가 따로
PROFILE_TABLES = {"agent": AGENT_PROFILES, "tool": TOOL_PROFILES}


def profile_env(kind: str, name: str) -> str:
    """프로필을 바꾸는 환경변수 이름 (agent, extraction → AGENT_EXTRACTION_MODEL_PROFILE)."""
    return f"{kind.upper()}_{name.upper()}_MODEL_PROFILE"


def _read_profiles(kind: str) -> dict[str, str]:
    """종류 하나의 이름 → 프로필 이름. 환경변수가 비면 표의 기본값."""
    return {
        name: os.environ.get(profile_env(kind, name), "").strip() or default
        for name, default in PROFILE_TABLES[kind].items()
    }


@dataclass(frozen=True)
class Settings:
    """AI 서버 설정. 키·접속 정보는 repr에 노출하지 않는다.

    Attributes:
        api_key: ML API 키 (OPENAI_API_KEY).
        base_url: ML API 주소 (OPENAI_BASE_URL).
        embedding_model: 임베딩 모델 이름 (OPENAI_EMBEDDING_MODEL).
        data_go_kr_key: 공공데이터포털 서비스 키 (DATA_GO_KR_KEY). 관세청 세관장확인·식약처가 사용.
        safetykorea_key: SafetyKorea AuthKey (KEY_SAFETYKOREA).
        law_oc: 법제처 OC 값 (LAW_GO_KR_OC).
        database_url: AI 전용 PostgreSQL 접속 문자열 (DATABASE_URL).
            개발 단계에서는 DB 없이도 서버를 띄울 수 있게 선택으로 둔다. 비어 있으면 DB 기능을 쓰지 않는다.
        agent_profiles: 에이전트 이름 → 프로필 이름. 기본은 AGENT_PROFILES.
        tool_profiles: Tool 이름 → 프로필 이름. 기본은 TOOL_PROFILES.

    Raises:
        ConfigError: 필수 설정이 비어 있거나 형식·허용 범위를 벗어난 경우.
    """

    api_key: str = field(repr=False)
    base_url: str = field(repr=False)
    embedding_model: str
    data_go_kr_key: str = field(repr=False)
    safetykorea_key: str = field(repr=False)
    law_oc: str = field(repr=False)
    database_url: str = field(repr=False)
    agent_profiles: dict[str, str] = field(default_factory=lambda: dict(AGENT_PROFILES))
    tool_profiles: dict[str, str] = field(default_factory=lambda: dict(TOOL_PROFILES))

    def __post_init__(self) -> None:

        # OpenAI API 키가 비어있는 경우
        if not self.api_key.strip():
            raise ConfigError("OPENAI_API_KEY가 비어 있습니다.")

        # ML API Base URL이 https://로 시작하지 않거나 /v1로 끝나지 않는 경우
        if not self.base_url.startswith("https://") or not self.base_url.rstrip("/").endswith("/v1"):
            # 팀별 엔드포인트 식별자가 오류 로그에 노출되지 않게 실제 값은 출력하지 않음.
            raise ConfigError("채팅 Base URL은 /v1로 끝나는 HTTPS 주소여야 합니다.")
        
        # 서버 기동을 위한 환경변수들을 모두 확인하여 비어 있는 것이 있는지 확인
        empty = [
            env_name
            for env_name, field_name in REQUIRED_ENV.items()
            if field_name not in ("api_key", "base_url") and not getattr(self, field_name).strip()
        ]

        # 비어 있는 필수 설정이 있는 경우
        if empty:
            raise ConfigError(f"필수 설정이 비어 있습니다: {', '.join(empty)}")
        
        # 비어 있는 것은 허용하지만(DB 미사용), 값을 넣었는데 형식이 틀린 경우
        if self.database_url and not self.database_url.startswith("postgresql"):
            # 접속 문자열에는 DB 비밀번호가 들어 있어 실제 값은 출력하지 않음.
            raise ConfigError("DATABASE_URL은 postgresql로 시작하는 접속 문자열이어야 합니다.")
        
        # 모르는 프로필 이름은 기본 프로필로 넘기지 않고 기동 실패
        unknown = [
            f"{profile_env(kind, name)}={profile!r}"
            for kind, profiles in (("agent", self.agent_profiles), ("tool", self.tool_profiles))
            for name, profile in profiles.items()
            if profile not in MODEL_PROFILES
        ]
        if unknown:
            wrong = ", ".join(unknown)
            raise ConfigError(f"없는 모델 프로필입니다: {wrong} (허용: {', '.join(MODEL_PROFILES)})")


def load_settings() -> Settings:
    """ai/.env와 환경변수에서 설정을 읽는다. 환경변수가 .env보다 우선한다.

    빠진 필수 환경변수는 하나씩이 아니라 한 번에 모아서 알려준다.
    기동이 실패했을 때 하나 고치고 다시 띄우기를 반복하지 않게 하기 위해서다.

    Returns:
        Settings: 검증을 마친 설정.

    Raises:
        ConfigError: 필수 환경변수가 없거나 값이 형식·허용 범위를 벗어난 경우.
    """

    # dotenv를 통한 환경변수 로드
    load_dotenv(dotenv_path=ENV_FILE, override=False, encoding="utf-8-sig")
    
    # 환경변수에서 설정값을 읽어 dict로 변환
    values = {
        field_name: os.environ.get(env_name, "").strip()
        for env_name, field_name in REQUIRED_ENV.items()
    }

    # 필수로 존재해야 하나 값이 없는 환경변수 필터링
    missing = [env_name for env_name, field_name in REQUIRED_ENV.items() if not values[field_name]]
    
    # 필수로 존재해야 하나 누락된 환경변수가 하나라도 존재하는 경우
    if missing:
        raise ConfigError(
            f"필수 환경변수가 없습니다: {', '.join(missing)}. "
            f"{ENV_FILE}에 설정하세요 (.env.example 참고)."
        )

    # Settings 객체를 생성하고 반환
    return Settings(
        **values,
        database_url=os.environ.get("DATABASE_URL", "").strip(),
        # 에이전트·Tool별 프로필. 환경변수가 있으면 기본값 대신 씀
        agent_profiles=_read_profiles("agent"),
        tool_profiles=_read_profiles("tool"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """프로세스 전체가 공유하는 설정을 돌려준다.

    처음 호출할 때 ``load_settings()``로 한 번 읽고 검증한 뒤 같은 객체를 계속 돌려준다.
    검증에 실패하면 예외는 캐시되지 않으므로, 다음 호출에서 다시 읽는다.

    Returns:
        Settings: 검증을 마친 공용 설정.

    Raises:
        ConfigError: 필수 환경변수가 없거나 값이 형식·허용 범위를 벗어난 경우.
    """
    return load_settings()
