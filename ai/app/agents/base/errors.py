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
    """모델 호출이 실패한 단계. 에이전트별 실패 문구를 고를 때 씀.

    CALL: 요청·전송 단계 실패 (응답 없음).
    PARSING: 응답은 받았으나 출력 해석 실패 (잘림·거절·스키마 위반 등).
    """

    CALL = "call"
    PARSING = "parsing"
