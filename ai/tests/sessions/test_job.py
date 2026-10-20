"""진단 함수 결말: 결과의 종료 사유와 결말 종류가 어긋나면 만들 때 거절하는지 확인한다."""

import pytest

from app.routers._dummy import build_dummy_assessment
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus
from app.sessions.job import JobDone, JobNeedsInput

_COMPLETED = build_dummy_assessment("p-1")
_AWAITING = _COMPLETED.model_copy(update={
    "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
    "verification_status": FinalVerificationStatus.INCOMPLETE,
})


def test_종료_사유가_맞으면_결말을_만든다():
    assert JobDone(_COMPLETED).result is _COMPLETED
    assert JobNeedsInput(_AWAITING).result is _AWAITING


def test_답변이_필요한_결과로_완료를_만들면_거절한다():
    with pytest.raises(ValueError):
        JobDone(_AWAITING)


def test_답변이_필요하지_않은_결과로_답변_대기를_만들면_거절한다():
    with pytest.raises(ValueError):
        JobNeedsInput(_COMPLETED)
