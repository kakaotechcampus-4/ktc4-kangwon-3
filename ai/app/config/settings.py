"""환경변수·ai/.env를 읽어 검증한 AI 서버 설정 (ML API · DB · 외부 API 키).

API 키는 저장소에 커밋하지 않고 ``ai/.env`` 또는 환경변수로 주입한다.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from .errors import ConfigError
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
    "INTERNAL_API_TOKEN": "internal_api_token",
    "BE_BASE_URL": "be_base_url",
}

# BE InternalApiProperties의 @Size(min = 32)와 같은 기준
INTERNAL_API_TOKEN_MIN_LENGTH = 32

# (선택) 개발용 진단 엔드포인트. 켤 때만 키 필수
DEV_API_ENABLED_ENV = "AI_DEV_API_ENABLED"
DEV_API_KEY_ENV = "AI_DEV_API_KEY"
DEV_API_KEY_MIN_LENGTH = 32
_TRUE_VALUES = ("true", "1", "yes", "on")
_FALSE_VALUES = ("false", "0", "no", "off", "")


# 프로필 표 종류. 덮어쓰기 값의 "종류.이름" 앞부분
PROFILE_TABLES = {"agent": AGENT_PROFILES, "tool": TOOL_PROFILES}

# (선택) 코드 기본값 대신 쓸 프로필. 벤치마크·긴급 전환용, 평소엔 비워 둠
OVERRIDES_ENV = "MODEL_PROFILE_OVERRIDES"


def parse_profile_overrides(raw: str) -> dict[tuple[str, str], str]:
    """덮어쓰기 값을 읽는다. 적은 대상만 바뀌고 나머지는 코드 기본값.

    Args:
        raw: "agent.extraction=luna-low,tool.electrical_safety=luna-low" 형식. 비면 덮어쓰기 없음.

    Returns:
        dict[tuple[str, str], str]: (종류, 이름) → 프로필 이름.

    Raises:
        ConfigError: 형식이 틀렸거나 프로필 표에 없는 대상인 경우 (오타가 조용히 무시되지 않게).
    """
    overrides: dict[tuple[str, str], str] = {}
    for item in filter(None, (part.strip() for part in raw.split(","))):
        target, _, profile = item.partition("=")
        kind, _, name = target.strip().partition(".")
        if not profile.strip() or kind not in PROFILE_TABLES or not name:
            raise ConfigError(f"{OVERRIDES_ENV} 형식은 '종류.이름=프로필'입니다 (종류: agent·tool): {item!r}")
        if name not in PROFILE_TABLES[kind]:
            raise ConfigError(f"{OVERRIDES_ENV}: 프로필 표에 없는 {kind}입니다: {name!r}")
        overrides[(kind, name)] = profile.strip()
    return overrides


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
        internal_api_token: BE 내부 API 토큰 (INTERNAL_API_TOKEN). 콜백 X-Internal-Token 헤더 값, BE와 같은 값.
        be_base_url: 콜백을 보낼 BE 주소 (BE_BASE_URL).
        dev_api_enabled: 개발용 진단 엔드포인트 켜기 (AI_DEV_API_ENABLED). 기본 꺼짐.
        dev_api_key: 개발용 진단 API 키 (AI_DEV_API_KEY). 켜져 있을 때만 필수, X-Dev-Api-Key 헤더 값.
            여러 사람에게 공유되는 값이라 콜백 토큰과 같으면 BE 내부 API에 가짜 결과를 넣을 수 있어 같은 값은 거부.
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
    internal_api_token: str = field(repr=False)
    be_base_url: str
    database_url: str = field(repr=False)
    dev_api_enabled: bool = False
    dev_api_key: str = field(default="", repr=False)
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

        # 토큰이 BE 기준보다 짧은 경우. 값은 출력하지 않음
        if len(self.internal_api_token.strip()) < INTERNAL_API_TOKEN_MIN_LENGTH:
            raise ConfigError(f"INTERNAL_API_TOKEN은 {INTERNAL_API_TOKEN_MIN_LENGTH}자 이상이어야 합니다.")

        # BE 주소가 http(s)://로 시작하지 않는 경우
        if not self.be_base_url.startswith(("http://", "https://")):
            raise ConfigError("BE_BASE_URL은 http:// 또는 https://로 시작해야 합니다.")

        # 개발용 진단을 켰으면 키 필수. 값은 출력하지 않음
        if self.dev_api_enabled:
            if len(self.dev_api_key.strip()) < DEV_API_KEY_MIN_LENGTH:
                raise ConfigError(f"{DEV_API_ENABLED_ENV}가 켜져 있으면 {DEV_API_KEY_ENV}가 "
                                  f"{DEV_API_KEY_MIN_LENGTH}자 이상이어야 합니다.")
            if self.dev_api_key.strip() == self.internal_api_token.strip():
                raise ConfigError(f"{DEV_API_KEY_ENV}는 INTERNAL_API_TOKEN과 다른 값이어야 합니다.")

        # 비어 있는 것은 허용하지만(DB 미사용), 값을 넣었는데 형식이 틀린 경우
        if self.database_url and not self.database_url.startswith("postgresql"):
            # 접속 문자열에는 DB 비밀번호가 들어 있어 실제 값은 출력하지 않음.
            raise ConfigError("DATABASE_URL은 postgresql로 시작하는 접속 문자열이어야 합니다.")
        
        # 모르는 프로필 이름은 기본 프로필로 넘기지 않고 기동 실패
        unknown = [
            f"{kind}.{name}={profile!r}"
            for kind, profiles in (("agent", self.agent_profiles), ("tool", self.tool_profiles))
            for name, profile in profiles.items()
            if profile not in MODEL_PROFILES
        ]
        if unknown:
            wrong = ", ".join(unknown)
            raise ConfigError(f"없는 모델 프로필입니다: {OVERRIDES_ENV}의 {wrong} (허용: {', '.join(MODEL_PROFILES)})")


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

    # 에이전트·Tool별 프로필. 덮어쓰기에 적은 대상만 기본값 대신 씀
    overrides = parse_profile_overrides(os.environ.get(OVERRIDES_ENV, ""))

    # Settings 객체를 생성하고 반환
    return Settings(
        **values,
        database_url=os.environ.get("DATABASE_URL", "").strip(),
        dev_api_enabled=_parse_bool(DEV_API_ENABLED_ENV, os.environ.get(DEV_API_ENABLED_ENV, "")),
        dev_api_key=os.environ.get(DEV_API_KEY_ENV, "").strip(),
        agent_profiles={name: overrides.get(("agent", name), default) for name, default in AGENT_PROFILES.items()},
        tool_profiles={name: overrides.get(("tool", name), default) for name, default in TOOL_PROFILES.items()},
    )


def _parse_bool(name: str, raw: str) -> bool:
    """켜기·끄기 환경변수를 읽는다. 오타가 조용히 꺼짐이 되지 않게 모르는 값은 거부.

    Raises:
        ConfigError: true·false·1·0·yes·no·on·off(대소문자 무시)나 빈 값이 아닌 경우.
    """
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(f"{name}은 true 또는 false여야 합니다.")


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
