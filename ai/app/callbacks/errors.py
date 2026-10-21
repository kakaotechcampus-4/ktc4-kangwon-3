"""콜백 전송 예외."""


class CallbackTransportError(RuntimeError):
    """응답을 받지 못한 전송 실패(타임아웃·연결 실패). 재시도 대상."""
