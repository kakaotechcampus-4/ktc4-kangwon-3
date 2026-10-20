"""진단 함수 한 번 실행. 진행 알림과 결말을 세션 상태 변경으로 바꿈."""

import logging
from typing import assert_never

from ...errors import AIResponseCode
from ...observability.context import ExecutionContext, PipelineStage
from ...schemas.agent import ExtractionInput
from ...schemas.schemas import ToolName
from ..job import DiagnosisJob, JobDone, JobFailed, JobNeedsInput, ToolProgressStatus
from ..transitions import AskUser, ChangeStage, Complete, Fail, ReportTool, Start
from .updater import SessionUpdater

logger = logging.getLogger(__name__)


class _Progress:
    """세션 하나의 진행 알림. 자기 실행(run_id)의 세션에만 적용."""

    def __init__(self, updater: SessionUpdater, context: ExecutionContext) -> None:
        self._updater = updater
        self._context = context

    def stage(self, stage: PipelineStage) -> None:
        self._updater.apply(self._context, ChangeStage(stage))

    def tool(self, tool_name: ToolName, status: ToolProgressStatus) -> None:
        self._updater.apply(self._context, ReportTool(tool_name, status))


def run_session(job: DiagnosisJob, item: ExtractionInput, context: ExecutionContext, updater: SessionUpdater) -> None:
    """세션 하나를 실행한다. 예외는 실패로 기록하고 밖으로 내보내지 않음.

    세션 변경은 모두 이 실행의 context로 함. 시간 초과 뒤 재접수된 새 세션은 건드리지 않음.

    Args:
        job: 진단 함수.
        item: 상품 입력.
        context: 이 실행의 컨텍스트.
        updater: 상태 변경 통로.
    """
    # 대기 중 시간 초과로 이미 실패한 세션이면 실행하지 않음
    if updater.apply(context, Start()) is None:
        return
    try:
        outcome = job(item, context, _Progress(updater, context))
    except Exception:
        logger.exception("진단 실행 실패 (product_id=%s, run_id=%s)", context.product_id, context.run_id)
        # 일시적 오류인지 알 수 없어 재시도 불가로 기록. 코드 오류를 BE가 계속 재요청하지 않게 함
        updater.apply(context, Fail(AIResponseCode.PIPELINE_ERROR.value.code, retryable=False))
        return
    match outcome:
        case JobDone(result=result):
            updater.apply(context, Complete(result))
        case JobNeedsInput(result=result):
            updater.apply(context, AskUser(result))
        case JobFailed(error_code=error_code, retryable=retryable):
            updater.apply(context, Fail(error_code, retryable))
        case _:
            assert_never(outcome)
