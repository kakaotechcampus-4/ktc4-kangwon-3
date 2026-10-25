"""이미지 선별 에이전트 예외."""

from ..base import AgentError


class ImageTriageFailedError(AgentError):
    """이미지 분류 모델 호출·파싱 실패, 또는 입력에 없는 이미지 번호를 돌려준 경우."""
