"""저장소·DB 연결 예외."""

from ..config import ConfigError


class DatabaseNotConfiguredError(ConfigError):
    """DATABASE_URL이 비어 있어 DB를 쓸 수 없다.

    개발 단계에서는 DB 없이도 서버를 띄울 수 있게 의도적으로 허용하는 상태라,
    설정이 틀린 경우(ConfigError)와 구분해서 기동 시 경고만 남긴다.
    """
