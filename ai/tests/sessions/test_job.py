"""진단 함수 결말의 종료 사유 검사와 실행 종류별 진단 함수 선택을 확인한다."""

import pytest

from app.domain.context import ExecutionContext, RunType
from app.routers._dummy import build_dummy_assessment
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus
from app.sessions.errors import UnsupportedRunTypeError
from app.sessions.job import JobDone, JobFailed, JobNeedsInput, by_run_type

_COMPLETED = build_dummy_assessment("p-1")
_AWAITING = _COMPLETED.model_copy(update={
    "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
    "verification_status": FinalVerificationStatus.INCOMPLETE,
})


def test_종료_사유가_맞으면_결말을_만든다():
    assert JobDone(_COMPLETED).result is _COMPLETED
    assert JobNeedsInput(_AWAITING, []).result is _AWAITING


def test_답변이_필요한_결과로_완료를_만들면_거절한다():
    with pytest.raises(ValueError):
        JobDone(_AWAITING)


def test_답변이_필요하지_않은_결과로_답변_대기를_만들면_거절한다():
    with pytest.raises(ValueError):
        JobNeedsInput(_COMPLETED, [])


def _context(run_type: RunType) -> ExecutionContext:
    return ExecutionContext.start(product_id="p-1", run_type=run_type)


def test_실행_종류에_맞는_진단_함수를_부른다():
    done, failed = JobDone(_COMPLETED), JobFailed("AI_PIPELINE_ERROR", retryable=False)
    job = by_run_type({
        RunType.PRODUCTION: lambda job_input, context, progress: done,
        RunType.DUMMY: lambda job_input, context, progress: failed,
    })

    assert job(None, _context(RunType.PRODUCTION), None) is done
    assert job(None, _context(RunType.DUMMY), None) is failed


def test_진단_함수가_없는_실행_종류는_거절한다():
    job = by_run_type({RunType.PRODUCTION: lambda job_input, context, progress: JobDone(_COMPLETED)})

    with pytest.raises(UnsupportedRunTypeError, match="dummy"):
        job(None, _context(RunType.DUMMY), None)
