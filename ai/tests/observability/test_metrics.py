"""세션 지표: 세션 이벤트로 소요 시간·횟수를 기록하고, 수집 때 세션 관리자 현황을 읽는지 확인한다."""

from datetime import datetime, timedelta, timezone

from prometheus_client import CollectorRegistry

from app.domain.context import ExecutionContext, PipelineStage, RunType
from app.observability.metrics import SessionMetrics, SessionSnapshotCollector
from app.routers._dummy import build_dummy_assessment
from app.schemas.agent import ExtractionInput
from app.schemas.callback import PublicQuestionDto
from app.schemas.schemas import ExecutionEndReason, FinalVerificationStatus, ToolName
from app.schemas.session import DiagnosisSession, SessionStatus
from app.sessions.events import SessionEvent
from app.sessions.manager import SessionSnapshot
from app.sessions.transitions import AskUser, Change, ChangeStage, Complete, Fail, ReportTool, Resume, Start, apply

ACCEPTED_AT = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


class _Run:
    """전이표대로 바꿔 가며 그 전이가 낸 이벤트를 돌려주는 실행 하나. 시각은 접수 후 몇 초인지로 줌."""

    def __init__(self, run_type: RunType = RunType.PRODUCTION) -> None:
        context = ExecutionContext.start(product_id="p-1", run_type=run_type, diagnosis_id="d-1")
        source = ExtractionInput(product_id="p-1", text_blocks=["상품 설명"])
        self.session = DiagnosisSession(context=context, source=source, accepted_at=ACCEPTED_AT, updated_at=ACCEPTED_AT)

    def __call__(self, change: Change, *, at: float) -> SessionEvent:
        [event] = apply(self.session, change, now=ACCEPTED_AT + timedelta(seconds=at)).events
        self.session = event.session
        return event


def _metrics() -> tuple[SessionMetrics, CollectorRegistry]:
    registry = CollectorRegistry()
    return SessionMetrics(registry), registry


def test_완료된_실행의_대기_실행_전체_단계_소요_시간을_기록한다():
    metrics, registry = _metrics()
    run = _Run()

    for event in (run(Start(), at=2), run(ChangeStage(PipelineStage.EXTRACTION), at=3),
                  run(ChangeStage(PipelineStage.SELECTION), at=8), run(Complete(build_dummy_assessment("p-1")), at=20)):
        metrics.on_event(event)

    def value(name, **labels):
        return registry.get_sample_value(name, {"run_type": "production", **labels})

    assert value("ai_session_queue_wait_seconds_sum") == 2
    assert value("ai_session_run_seconds_sum", outcome="completed") == 18
    assert value("ai_session_total_seconds_sum", outcome="completed") == 20
    assert value("ai_session_stage_seconds_sum", stage="extraction") == 5
    assert value("ai_session_stage_seconds_sum", stage="selection") == 12
    assert value("ai_session_finished_total", outcome="completed") == 1


def test_대기_중_시간_초과는_실행_시간_없이_실패로_센다():
    metrics, registry = _metrics()

    metrics.on_event(_Run()(Fail("AI_TIMEOUT", retryable=True), at=600))

    labels = {"run_type": "production", "outcome": "failed"}
    assert registry.get_sample_value("ai_session_total_seconds_sum", labels) == 600
    assert registry.get_sample_value("ai_session_run_seconds_count", labels) is None
    assert registry.get_sample_value(
        "ai_session_failed_total", {"run_type": "production", "error_code": "AI_TIMEOUT"}) == 1


def test_재진단_실행은_재접수_시각부터_따로_잰다():
    metrics, registry = _metrics()
    run = _Run()
    awaiting = build_dummy_assessment("p-1").model_copy(update={
        "termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED,
        "verification_status": FinalVerificationStatus.INCOMPLETE,
    })
    questions = [PublicQuestionDto(question_key="battery_only", question_order=1, question_text="배터리 전용인가요?")]
    new_context = ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION, diagnosis_id="d-1")

    for event in (run(Start(), at=1), run(AskUser(awaiting, questions), at=10),
                  run(Resume(new_context, []), at=100), run(Start(), at=103),
                  run(Complete(build_dummy_assessment("p-1")), at=110)):
        metrics.on_event(event)

    def value(name, **labels):
        return registry.get_sample_value(name, {"run_type": "production", **labels})

    assert value("ai_session_queue_wait_seconds_sum") == 1 + 3
    assert value("ai_session_total_seconds_sum", outcome="completed") == 10
    assert value("ai_session_run_seconds_sum", outcome="completed") == 7


def test_Tool_진행을_Tool과_상태별로_센다():
    metrics, registry = _metrics()
    run = _Run(RunType.TEST)
    run(Start(), at=0)
    run(ChangeStage(PipelineStage.TOOL_EXECUTION), at=1)

    metrics.on_event(run(ReportTool(ToolName.ELECTRICAL, "started"), at=2))
    metrics.on_event(run(ReportTool(ToolName.ELECTRICAL, "completed"), at=3))

    labels = {"run_type": "test", "tool_name": ToolName.ELECTRICAL.value}
    assert registry.get_sample_value("ai_session_tool_progress_total", {**labels, "status": "started"}) == 1
    assert registry.get_sample_value("ai_session_tool_progress_total", {**labels, "status": "completed"}) == 1


class _Manager:
    def snapshot(self) -> SessionSnapshot:
        counts = dict.fromkeys(SessionStatus, 0) | {SessionStatus.ACCEPTED: 3, SessionStatus.RUNNING: 2}
        return SessionSnapshot(
            status_counts=counts,
            inflight=5, dev_inflight=1, max_running=2, max_inflight=10, max_dev_inflight=2,
            accepted={run_type: 0 for run_type in RunType} | {RunType.PRODUCTION: 7},
            rejected={"queue_full": 1, "conflict": 4},
        )


def test_수집_때_세션_관리자_현황을_지표로_낸다():
    registry = CollectorRegistry()
    registry.register(SessionSnapshotCollector(_Manager()))

    def value(name, **labels):
        return registry.get_sample_value(name, labels)

    assert (value("ai_sessions", status="accepted"), value("ai_sessions", status="running")) == (3, 2)
    assert value("ai_sessions", status="failed") == 0
    assert (value("ai_session_slots_used", scope="all"), value("ai_session_slots_used", scope="dev")) == (5, 1)
    assert [value("ai_session_slots_limit", scope=scope) for scope in ("all", "dev", "running")] == [10, 2, 2]
    assert value("ai_session_accepted_total", run_type="production") == 7
    assert (value("ai_session_rejected_total", reason="queue_full"),
            value("ai_session_rejected_total", reason="conflict")) == (1, 4)
