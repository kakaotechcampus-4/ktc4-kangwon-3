"""BE 클라이언트 예외."""

from ..errors import ClientError


class CallbackTransportError(ClientError, RuntimeError):
    """응답을 받지 못한 전송 실패(타임아웃·연결 실패). 재시도 대상."""
