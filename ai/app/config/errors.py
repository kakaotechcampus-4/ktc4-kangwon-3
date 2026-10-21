"""설정 예외."""


class ConfigError(RuntimeError):
    """AI 서버 설정이 없거나 허용 범위를 벗어났다."""
