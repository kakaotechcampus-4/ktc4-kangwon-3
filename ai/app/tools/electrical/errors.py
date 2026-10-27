"""전기안전 Tool 예외."""

from ..base import ToolModelError


class ElectricalToolError(ToolModelError):
    """모델·외부 자료 실패. 원본 오류는 예외 체인에만 보존한다."""
