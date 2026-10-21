"""진단 세션 상태 변경을 BE 콜백 이벤트로 바꾼다 (#310).

SessionExecutor.subscribe()로 받은 세션마다 보낼 이벤트 목록을 만듦.
    - 단계 변경 → 진행 이벤트 (앞 단계 completed + 새 단계 started)
    - Tool 진행(subscribe_tool) → toolName 붙은 진행 이벤트. Tool 실행 단계 안에서만
    - 답변 대기 → 질문 이벤트, 완료 → 결과 이벤트, 실패·시간 초과 → 실패 이벤트
질문·결과·실패는 그 실행(runId)의 마지막. 이후 같은 실행의 변경은 이벤트를 만들지 않음.
진단서 변환(result_status 결정)은 주입받은 AssessmentPresenter가 맡음.
질문 회차·질문은 실행기가 세션에 기록한 값을 그대로 씀 (재진단 답변 검사와 같은 기준).
변환이 실패하면 실패 이벤트로 끝냄 (마지막 이벤트가 빠지면 BE에서 진행 중으로 남음).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Protocol
from uuid import uuid4

from ..errors import AIResponseCode
from ..observability.context import PipelineStage
from ..schemas.callback import (
    ProductAwaitingInputEvent, ProductFailedEvent, ProductProgressEvent, ProductResultEvent, PublicAssessmentDto,
    PublicErrorDto, PublicPipelineStage, PublicProductEvent, PublicQuestionDto,
)
from ..schemas.schemas import FinalAssessment, ToolName
from ..schemas.session import DiagnosisSession, SessionStatus
from ..sessions.executor import ToolProgressStatus

_PUBLIC_STAGES = {stage.value: stage for stage in PublicPipelineStage}
_ERROR_MESSAGES = {code.value.code: code.value.message for code in AIResponseCode}
_DEFAULT_ERROR_MESSAGE = AIResponseCode.PIPELINE_ERROR.value.message
# 진단서·질문 변환 실패 표시
_CONVERSION_FAILED = object()

logger = logging.getLogger(__name__)


class AssessmentPresenter(Protocol):
    """완료 결과를 BE에 공개할 진단서로 바꾸는 쪽."""

    def assessment(self, result: FinalAssessment) -> PublicAssessmentDto:
        """완료 결과의 공개 진단서."""
        ...


@dataclass
class _RunState:
    """실행 하나의 이벤트 진행. sequence는 다음에 쓸 번호."""

    sequence: int = 1
    stage: PublicPipelineStage | None = None


class EventBuilder:
    """세션 상태 변경을 콜백 이벤트로 바꾼다. 여러 실행 스레드에서 동시에 불려도 됨.

    Args:
        presenter: 진단서 변환.
        new_event_id: 이벤트 ID 생성 함수. 테스트에서 고정할 때 주입.
    """

    def __init__(self, presenter: AssessmentPresenter, *, new_event_id: Callable[[], str] = lambda: str(uuid4())):
        self._presenter = presenter
        self._new_event_id = new_event_id
        self._lock = Lock()
        self._runs: dict[str, _RunState] = {}
        self._finished: set[str] = set()

    def build(self, session: DiagnosisSession) -> list[PublicProductEvent]:
        """세션 한 건의 변경으로 보낼 이벤트를 만든다.

        Args:
            session: 바뀐 세션.

        Returns:
            list[PublicProductEvent]: 보낼 순서대로. 보낼 게 없으면 빈 목록
                (진단서 없는 실행, 끝난 실행, 단계 변화 없음).
        """
        context = session.context
        # 평가·테스트 실행은 BE 진단서가 없어 보내지 않음
        if context.diagnosis_id is None:
            return []
        # 잠금 밖에서 내용부터 만듦. 실패하면 실패 이벤트로 끝냄
        try:
            content = self._content(session)
        except Exception:
            logger.exception("콜백 진단서·질문 변환 실패 (product_id=%s, run_id=%s)",
                             context.product_id, context.run_id)
            content = _CONVERSION_FAILED
        with self._lock:
            if context.run_id in self._finished:
                return []
            run = self._runs.setdefault(context.run_id, _RunState())
            if session.status is SessionStatus.RUNNING:
                return self._progress(session, run)
            if isinstance(content, PublicAssessmentDto):
                event = ProductResultEvent(**self._base(session, run), assessment=content)
            elif content is _CONVERSION_FAILED:
                # 세션은 완료·답변 대기라 오류 코드가 비어 있음. 실행기의 파이프라인 오류와 같게 재시도 불가
                event = self._failed(session, run, code=AIResponseCode.PIPELINE_ERROR.value.code, retryable=False)
            elif content is not None:
                question_round, questions = content
                event = ProductAwaitingInputEvent(
                    **self._base(session, run), question_round=question_round, questions=questions,
                )
            elif session.status is SessionStatus.FAILED:
                event = self._failed(session, run)
            else:
                return []
            del self._runs[context.run_id]
            # 끝난 실행 ID만 남김 (실행당 문자열 하나)
            self._finished.add(context.run_id)
            return [event]

    def build_tool(
        self, session: DiagnosisSession, tool_name: ToolName, status: ToolProgressStatus,
    ) -> list[PublicProductEvent]:
        """Tool 진행 하나를 진행 이벤트로 바꾼다. 단계 이벤트와 번호를 이어 씀.

        Args:
            session: Tool 진행 시점의 세션.
            tool_name: 내부 Tool 이름. BE에는 PublicToolName(멤버 이름, 예: ELECTRICAL)으로 보냄.
            status: Tool 진행 상태.

        Returns:
            list[PublicProductEvent]: 보낼 이벤트 하나. 보낼 게 없으면 빈 목록
                (진단서 없는 실행, 끝난 실행, Tool 실행 단계 시작 전).
        """
        context = session.context
        if context.diagnosis_id is None:
            return []
        with self._lock:
            if context.run_id in self._finished:
                return []
            run = self._runs.setdefault(context.run_id, _RunState())
            # 단계 시작을 알리기 전의 Tool 진행은 버림. 단계 경로와 섞지 않음
            if run.stage is not PublicPipelineStage.TOOL_EXECUTION:
                logger.warning("Tool 실행 단계 시작 전 Tool 진행은 보내지 않음 (product_id=%s, run_id=%s, tool=%s)",
                               context.product_id, context.run_id, tool_name)
                return []
            return [ProductProgressEvent(**self._base(session, run), stage=run.stage, stage_status=status,
                                         tool_name=tool_name.name)]

    def _content(
        self, session: DiagnosisSession,
    ) -> PublicAssessmentDto | tuple[int, list[PublicQuestionDto]] | None:
        """완료면 공개 진단서, 답변 대기면 세션에 기록된 (질문 회차, 질문). 그 외는 None."""
        if session.result is None:
            return None
        if session.status is SessionStatus.COMPLETED:
            return self._presenter.assessment(session.result)
        if session.status is SessionStatus.AWAITING_INPUT:
            return session.question_round, session.questions
        return None

    def _progress(self, session: DiagnosisSession, run: _RunState) -> list[PublicProductEvent]:
        """단계가 바뀌었으면 앞 단계 completed + 새 단계 started. 내부 전용 단계는 건너뜀."""
        stage = _public_stage(session.stage)
        if stage is None or stage is run.stage:
            return []
        events: list[PublicProductEvent] = []
        if run.stage is not None:
            events.append(ProductProgressEvent(**self._base(session, run), stage=run.stage, stage_status="completed"))
        events.append(ProductProgressEvent(**self._base(session, run), stage=stage, stage_status="started"))
        run.stage = stage
        return events

    def _failed(
        self, session: DiagnosisSession, run: _RunState, *, code: str | None = None, retryable: bool | None = None,
    ) -> ProductFailedEvent:
        """실패 이벤트. code·retryable을 주지 않으면 세션 값, 세션에도 없으면 파이프라인 오류."""
        code = code or session.error_code or AIResponseCode.PIPELINE_ERROR.value.code
        return ProductFailedEvent(
            **self._base(session, run),
            stage=_public_stage(session.stage),
            error=PublicErrorDto(code=code, message=_ERROR_MESSAGES.get(code, _DEFAULT_ERROR_MESSAGE),
                                 retryable=session.retryable if retryable is None else retryable),
        )

    def _base(self, session: DiagnosisSession, run: _RunState) -> dict:
        """공통 필드. 부를 때마다 sequence 1 증가."""
        context = session.context
        base = {
            "event_id": self._new_event_id(), "diagnosis_id": context.diagnosis_id,
            "product_id": context.product_id, "run_id": context.run_id, "sequence": run.sequence,
        }
        run.sequence += 1
        return base


def _public_stage(stage: PipelineStage | None) -> PublicPipelineStage | None:
    """내부 단계를 공개 단계로. 공개하지 않는 단계(pipeline)·실행 전이면 None."""
    return _PUBLIC_STAGES.get(stage.value) if stage is not None else None
