"""설정 예외."""

from ..domain.errors import AIError


class ConfigError(AIError, RuntimeError):
    """AI 서버 설정이 없거나 허용 범위를 벗어났다."""
