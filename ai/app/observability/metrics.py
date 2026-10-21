"""진단 세션·에이전트 지표를 Prometheus 형식으로 모음. GET /metrics가 registry를 그대로 내보냄.

    - SessionMetrics: 세션 이벤트 구독자. 대기·실행·전체·단계 소요 시간과 결말·Tool 진행 횟수
    - SessionSnapshotCollector: 수집(scrape) 때마다 세션 관리자 현황을 읽음. 상태별 수·자리·상한·누적 접수/거절
    - AgentMetrics: 에이전트 실행 기록 sink. 모델 호출 수·토큰·비용·호출 시간

라벨에 product_id·run_id는 넣지 않음 (실행마다 시계열이 늘어남). 세션 지표는 실행 종류(run_type)로 운영·개발 구분.
에이전트 지표는 실행 컨텍스트가 없어 기록 이름(평가 호출은 extraction-eval 등)으로만 구분.
"""

from collections.abc import Iterator
from datetime import datetime
from threading import Lock

from prometheus_client import CollectorRegistry, Counter, Histogram
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, Metric
from prometheus_client.registry import Collector

from ..agents.base.meta import AgentRunMeta
from ..sessions.events import AwaitingInput, Completed, Failed, SessionEvent, StageChanged, Started, ToolProgressed
from ..sessions.manager import SessionManager

# 세션 소요 시간 구간(초). 세션 최대 시간(SESSION_MAX_DURATION_SECONDS, 600초)까지
DURATION_BUCKETS = (1, 5, 10, 30, 60, 120, 300, 600)
# 모델 호출 1건 소요 시간 구간(초)
AGENT_CALL_BUCKETS = (0.5, 1, 2, 5, 10, 20, 30, 60, 120)

_OUTCOMES = {Completed: "completed", AwaitingInput: "awaiting_input", Failed: "failed"}


class SessionMetrics:
    """세션 이벤트로 소요 시간·횟수를 기록한다. SessionManager.subscribe에 on_event를 등록해 씀."""

    def __init__(self, registry: CollectorRegistry) -> None:
        """지표를 registry에 등록한다.

        Args:
            registry: 지표를 등록할 registry. 테스트마다 새로 만들 수 있게 주입.
        """
        self._queue_wait = Histogram(
            "ai_session_queue_wait_seconds", "접수부터 실행 시작까지 대기 시간",
            ["run_type"], buckets=DURATION_BUCKETS, registry=registry,
        )
        self._run = Histogram(
            "ai_session_run_seconds", "실행 시작부터 결말까지 실행 시간",
            ["run_type", "outcome"], buckets=DURATION_BUCKETS, registry=registry,
        )
        self._total = Histogram(
            "ai_session_total_seconds", "접수부터 결말까지 전체 소요 시간",
            ["run_type", "outcome"], buckets=DURATION_BUCKETS, registry=registry,
        )
        self._stage = Histogram(
            "ai_session_stage_seconds", "실행 단계 하나의 소요 시간",
            ["run_type", "stage"], buckets=DURATION_BUCKETS, registry=registry,
        )
        self._finished = Counter(
            "ai_session_finished", "결말별 끝난 세션 수", ["run_type", "outcome"], registry=registry,
        )
        self._failed = Counter(
            "ai_session_failed", "오류 코드별 실패한 세션 수", ["run_type", "error_code"], registry=registry,
        )
        self._tool = Counter(
            "ai_session_tool_progress", "Tool 진행 알림 수", ["run_type", "tool_name", "status"], registry=registry,
        )
        self._lock = Lock()
        # 실행별 지금 단계와 그 시작 시각. 다음 단계 변경·결말 때 앞 단계 소요 시간을 재고 지움
        self._stages: dict[str, tuple[str, datetime]] = {}

    def on_event(self, event: SessionEvent) -> None:
        """세션 이벤트 하나를 기록한다.

        Args:
            event: 세션 이벤트.
        """
        session = event.session
        run_type = session.context.run_type.value
        match event:
            case Started():
                self._queue_wait.labels(run_type).observe(_seconds(session.accepted_at, session.started_at))
            case StageChanged(stage=stage):
                self._close_stage(session.context.run_id, run_type, session.updated_at)
                with self._lock:
                    self._stages[session.context.run_id] = (stage.value, session.updated_at)
            case ToolProgressed(tool_name=tool_name, status=status):
                self._tool.labels(run_type, tool_name.value, status).inc()
            case Completed() | AwaitingInput() | Failed():
                outcome = _OUTCOMES[type(event)]
                self._close_stage(session.context.run_id, run_type, session.updated_at)
                self._finished.labels(run_type, outcome).inc()
                self._total.labels(run_type, outcome).observe(_seconds(session.accepted_at, session.updated_at))
                # 대기 중 시간 초과로 실패하면 실행 시작이 없음
                if session.started_at is not None:
                    self._run.labels(run_type, outcome).observe(_seconds(session.started_at, session.updated_at))
                if isinstance(event, Failed):
                    self._failed.labels(run_type, event.error_code).inc()

    def _close_stage(self, run_id: str, run_type: str, now: datetime) -> None:
        """실행의 지금 단계를 끝내고 소요 시간을 기록한다. 단계가 없으면 아무것도 안 함."""
        with self._lock:
            current = self._stages.pop(run_id, None)
        if current is not None:
            stage, started_at = current
            self._stage.labels(run_type, stage).observe(_seconds(started_at, now))


class SessionSnapshotCollector(Collector):
    """수집 때마다 세션 관리자 현황을 읽어 지표로 바꾼다."""

    def __init__(self, manager: SessionManager) -> None:
        """현황을 읽을 세션 관리자를 받는다.

        Args:
            manager: 세션 관리자.
        """
        self._manager = manager

    def collect(self) -> Iterator[Metric]:
        """현황 지표를 만든다.

        Returns:
            Iterator[Metric]: 상태별 수, 자리 사용·상한, 누적 접수·거절.
        """
        snapshot = self._manager.snapshot()

        sessions = GaugeMetricFamily("ai_sessions", "상태별 보관 중인 세션 수", labels=["status"])
        for status, count in snapshot.status_counts.items():
            sessions.add_metric([status.value], count)
        yield sessions

        used = GaugeMetricFamily("ai_session_slots_used", "차지한 대기 + 실행 중 자리 수", labels=["scope"])
        used.add_metric(["all"], snapshot.inflight)
        used.add_metric(["dev"], snapshot.dev_inflight)
        yield used

        limit = GaugeMetricFamily("ai_session_slots_limit", "자리 상한", labels=["scope"])
        limit.add_metric(["all"], snapshot.max_inflight)
        limit.add_metric(["dev"], snapshot.max_dev_inflight)
        limit.add_metric(["running"], snapshot.max_running)
        yield limit

        accepted = CounterMetricFamily("ai_session_accepted", "누적 접수 세션 수", labels=["run_type"])
        for run_type, count in snapshot.accepted.items():
            accepted.add_metric([run_type.value], count)
        yield accepted

        rejected = CounterMetricFamily("ai_session_rejected", "사유별 누적 거절 요청 수", labels=["reason"])
        for reason, count in snapshot.rejected.items():
            rejected.add_metric([reason], count)
        yield rejected


class AgentMetrics:
    """에이전트 모델 호출 기록으로 호출 수·토큰·비용·시간을 기록한다. agent_sinks에 on_run을 등록해 씀."""

    def __init__(self, registry: CollectorRegistry) -> None:
        """지표를 registry에 등록한다.

        Args:
            registry: 지표를 등록할 registry. 테스트마다 새로 만들 수 있게 주입.
        """
        self._calls = Counter(
            "ai_agent_calls", "결과별 모델 호출 수. outcome은 ok 또는 실패 단계(call·parsing·finalize)",
            ["component", "model", "outcome"], registry=registry,
        )
        self._tokens = Counter(
            "ai_agent_tokens", "종류별 토큰 수. cached는 input에, reasoning은 output에 포함",
            ["component", "model", "kind"], registry=registry,
        )
        self._cost = Counter(
            "ai_agent_cost_krw", "예상 비용(원). 단가를 모르는 모델은 빠짐", ["component", "model"], registry=registry,
        )
        self._call_seconds = Histogram(
            "ai_agent_call_seconds", "모델 호출 1건 소요 시간",
            ["component", "outcome"], buckets=AGENT_CALL_BUCKETS, registry=registry,
        )

    def on_run(self, meta: AgentRunMeta, subject_id: str) -> None:
        """모델 호출 1건을 기록한다.

        Args:
            meta: 호출 1건의 실행 정보.
            subject_id: 기록 대상 ID. 라벨에 넣지 않음.
        """
        component = meta.usage_name or meta.component
        model = meta.model or "none"
        # 실패 단계를 모르는 실패는 failed
        outcome = "ok" if meta.error_type is None else meta.failure_phase or "failed"
        self._calls.labels(component, model, outcome).inc()
        self._call_seconds.labels(component, outcome).observe(meta.elapsed_ms / 1000)
        if meta.usage is not None:
            for kind, count in (("input", meta.usage.input_tokens), ("cached", meta.usage.cached_tokens),
                                ("output", meta.usage.output_tokens), ("reasoning", meta.usage.reasoning_tokens)):
                self._tokens.labels(component, model, kind).inc(count)
        if meta.cost_krw is not None:
            self._cost.labels(component, model).inc(meta.cost_krw)


def _seconds(start: datetime, end: datetime) -> float:
    """두 시각 사이 초. 시계가 뒤로 가도 음수는 내지 않음."""
    return max((end - start).total_seconds(), 0.0)
