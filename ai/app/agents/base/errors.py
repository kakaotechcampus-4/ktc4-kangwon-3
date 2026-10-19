"""에이전트 공통 예외와 실패 단계."""

from enum import StrEnum


class AgentError(RuntimeError):
    """에이전트 모델 호출·파싱 실패의 공통 부모.

    Attributes:
        partial_result: 실패 전까지 만든 부분 결과. 없으면 None.
    """

    def __init__(self, message: str, *, partial_result: object | None = None) -> None:
        super().__init__(message)
        self.partial_result = partial_result


class MissingParsedOutput(RuntimeError):
    """파싱 오류 없이 구조화 출력이 비어 온 경우의 원인 예외."""


class ModelFailurePhase(StrEnum):
    CALL = "call"
    PARSING = "parsing"
