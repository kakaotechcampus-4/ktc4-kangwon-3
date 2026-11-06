"""HTTP 접수부터 BE 콜백까지 실제 진단 흐름을 확인한다.

세션·진단 함수(job)·파이프라인 순서(runner)·Tool 실행·집계·질문 만들기·콜백 발신함은 실제 코드.
모델·외부 호출 자리(추출·Tool 선택·Tool·검증 에이전트, 입력 가드 판정)만 가짜, BE는 httpx.MockTransport.
콜백은 BE 계약 키(eventType·runId·sequence·단계·질문·오류·결과 요약)만 비교.
"""

import json
import logging
import threading
import time
from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.agents.input_guard import GuardOutcome, GuardVerdict
from app.clients.backend import BackendCallbackClient
from app.db import engine as database
from app.diagnosis import build_job, build_questions, guarded
from app.diagnosis.assembly import PipelineParts
from app.dummy import run_case_diagnosis
from app.observability.logs import APP_LOGGER
from app.pipeline.aggregator import ResultAggregator
from app.pipeline.extraction_step import ExtractionStep
from app.schemas.agent import ToolSelectionItem, ToolSelectionResponse
from app.schemas.product import Product
from app.schemas.schemas import FollowUpQuestion, ToolName, ToolResult, ToolStatus, VerificationResult, VerificationStatus
from app.sessions.manager import SessionManager
from app.startup import parts as startup

TOKEN = "test-internal-token-0123456789abcdef"
_ENV = {
    "OPENAI_API_KEY": "test-key",
    "OPENAI_BASE_URL": "https://mlapi.run/example/v1",
    "OPENAI_EMBEDDING_MODEL": "openai/text-embedding-3-small",
    "DATA_GO_KR_KEY": "test-data-key",
    "KEY_SAFETYKOREA": "test-safety-key",
    "LAW_GO_KR_OC": "test-oc",
    "INTERNAL_API_TOKEN": TOKEN,
    "BE_BASE_URL": "http://be-server:8080",
    "REVIEW_TEXT_HIGH": "0.85",
    "REVIEW_TEXT_LOW": "0.3",
    "REVIEW_IMAGE_HIGH": "0.8",
    "REVIEW_IMAGE_LOW": "0.3",
}
CONTENT = "/api/ai/v1/diagnose/content"
RESUME = "/api/ai/v1/diagnose/resume"
QUESTION = FollowUpQuestion(question="몇 세 이상이 쓰는 제품인가요?", reason="어린이 제품인지 판단")

# 전기용품 Tool 하나만 고른 첫 회차의 진행 콜백 (단계, 상태, Tool)
FIRST_ROUND = [
    ("extraction", "started", None), ("extraction", "completed", None),
    ("selection", "started", None), ("selection", "completed", None),
    ("tool_execution", "started", None),
    ("tool_execution", "started", "ELECTRICAL"), ("tool_execution", "completed", "ELECTRICAL"),
    *[("tool_execution", "skipped", tool) for tool in ("CUSTOMS", "RADIO", "FOOD_DRUG", "CHILDREN", "LABEL_AD")],
    ("tool_execution", "completed", None),
    ("aggregation", "started", None), ("aggregation", "completed", None),
    ("verification", "started", None), ("verification", "completed", None),
]
# 검증이 전파 Tool을 더 요청한 재실행 회차 (건너뜀은 다시 보내지 않음)
RETRY_ROUND = [
    ("tool_execution", "started", None),
    ("tool_execution", "started", "RADIO"), ("tool_execution", "completed", "RADIO"),
    ("tool_execution", "completed", None),
    ("aggregation", "started", None), ("aggregation", "completed", None),
    ("verification", "started", None), ("verification", "completed", None),
]
FINALIZATION = [("finalization", "started", None)]


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    """실제 ai/.env·DB·Sentry 없이 기동할 설정. lifespan이 붙인 app 로그 핸들러·레벨은 끝나고 되돌림."""
    monkeypatch.setattr(config.settings, "load_dotenv", lambda **kwargs: False)
    for name, value in _ENV.items():
        monkeypatch.setenv(name, value)
    for name in ("DATABASE_URL", "MODEL_PROFILE_OVERRIDES", "AI_DEV_API_ENABLED", "AI_DEV_API_KEY",
                 "SENTRY_DSN", "SENTRY_ENVIRONMENT"):
        monkeypatch.delenv(name, raising=False)
    caches = (config.get_settings, database.get_engine, database.get_session_factory)
    for cached in caches:
        cached.cache_clear()
    logger = logging.getLogger(APP_LOGGER)
    handlers, level = list(logger.handlers), logger.level
    yield
    logger.handlers[:] = handlers
    logger.setLevel(level)
    for cached in caches:
        cached.cache_clear()


class _Backend:
    """콜백을 받는 가짜 BE. respond로 이벤트마다 응답 상태를 정함 (기본 200)."""

    def __init__(self, respond: Callable[[dict], int] = lambda event: 200):
        self.received: list[tuple[dict, int]] = []
        self._respond = respond
        self._lock = threading.Lock()

    def handle(self, request: httpx.Request) -> httpx.Response:
        event = json.loads(request.content)
        with self._lock:
            status = self._respond(event)
            self.received.append((event, status))
        code = "OK" if status == 200 else "COMMON-001"
        return httpx.Response(status, json={"code": code, "message": "", "data": None})

    def accepted(self) -> list[dict]:
        """200으로 받은 이벤트 (받은 순서)."""
        with self._lock:
            return [event for event, status in self.received if status == 200]

    def wait_for(self, event_type: str, timeout: float = 5.0) -> dict:
        """그 종류 이벤트를 200으로 받을 때까지 기다려 마지막 것을 돌려준다."""
        deadline = time.monotonic() + timeout
        while not (found := [event for event in self.accepted() if event["eventType"] == event_type]):
            if time.monotonic() > deadline:
                raise AssertionError(f"{event_type} 콜백을 기다리다 시간 초과: {self.received}")
            time.sleep(0.01)
        return found[-1]


class _Agents:
    """모델·외부 호출 자리 가짜. 고를 Tool·실패할 Tool·검증 회차별 상태·가드 판정을 정해 두고, 부른 기록을 남김."""

    def __init__(self, *, failing=(), verifications=(VerificationStatus.APPROVED,), guard=GuardOutcome.PASS):
        self.failing = set(failing)
        self.verifications = list(verifications)
        self.guard = guard
        self.extracted: list = []
        self.executed: list[ToolName] = []

    def run(self, source) -> Product:
        """추출 에이전트 자리."""
        self.extracted.append(source)
        return Product(product_id=source.product_id, product_name="무선 선풍기")

    def select(self, product: Product) -> ToolSelectionResponse:
        return ToolSelectionResponse(decisions=[
            ToolSelectionItem(tool_name=name, selected=name is ToolName.ELECTRICAL, reason="가짜 선택")
            for name in ToolName])

    def tool(self, name: ToolName):
        agents = self

        class _Tool:
            tool_name = name

            def execute(self, product, decision):
                agents.executed.append(name)
                if name in agents.failing:
                    raise RuntimeError("가짜 조회 실패")
                return ToolResult(tool_name=name, status=ToolStatus.SUCCESS, selected=True,
                                  selection_reason=decision.reason)

        return _Tool()

    def verify(self, draft) -> VerificationResult:
        """회차마다 정해 둔 상태를 차례로, 마지막 상태는 계속."""
        status = self.verifications.pop(0) if len(self.verifications) > 1 else self.verifications[0]
        return VerificationResult(
            status=status,
            additional_tools_required=[ToolName.RADIO] if status is VerificationStatus.TOOLS_REQUIRED else [],
            follow_up_questions=[QUESTION] if status is VerificationStatus.USER_INPUT_REQUIRED else [],
        )

    def judge(self, guard_input) -> GuardVerdict:
        return GuardVerdict(outcome=self.guard)

    def job(self):
        """실제 조립(build_job·guarded)에 가짜 에이전트만 끼운 운영 진단 함수."""
        parts = PipelineParts(
            # URL 수집기는 글이 있는 입력이라 안 부름
            extraction=ExtractionStep(self, url_builder=None),
            selector=type("Selector", (), {"run": staticmethod(self.select)})(),
            tools={name: self.tool(name) for name in ToolName},
            aggregator=ResultAggregator(),
            verifier=type("Verifier", (), {"run": staticmethod(self.verify)})(),
        )
        return guarded(build_job(parts, build_questions), self.judge, delay=(0, 0))


def _client(agents: _Agents, backend: _Backend) -> TestClient:
    parts = startup.AppParts(
        pipeline_job=agents.job(),
        dummy_job=run_case_diagnosis,
        callback_sender=BackendCallbackClient("http://be-server:8080", TOKEN,
                                              transport=httpx.MockTransport(backend.handle)),
        database=None,
        session_manager=SessionManager,
        sweep_seconds=config.SESSION_SWEEP_SECONDS,
        drain_seconds=config.SESSION_DRAIN_SECONDS,
    )
    return TestClient(main.create_app(lambda settings: parts), headers={"X-Internal-Token": TOKEN})


def _submit(client: TestClient) -> str:
    response = client.post(CONTENT, json={
        "diagnosisId": "d-1", "products": [{"productId": "p-1", "textBlocks": ["무선 선풍기 USB 충전"]}],
    })
    assert response.status_code == 202
    [accepted] = response.json()["data"]["products"]
    return accepted["runId"]


def _run(events: list[dict], run_id: str) -> list[dict]:
    """한 실행의 이벤트. 순번이 1부터 빠짐없이 이어지는지도 확인."""
    run = [event for event in events if event["runId"] == run_id]
    assert [event["sequence"] for event in run] == list(range(1, len(run) + 1))
    return run


def _progress(run: list[dict]) -> list[tuple]:
    return [(event["stage"], event["stageStatus"], event["toolName"])
            for event in run if event["eventType"] == "product_progress"]


def _reviews(result: dict) -> dict[str, str]:
    """검토한 분야(건너뜀 제외) → 상태."""
    return {review["toolName"]: review["status"] for review in result["assessment"]["toolReviews"]
            if review["status"] != "SKIPPED"}


def test_진단이_끝나면_단계별_진행과_결과가_순서대로_BE_콜백으로_나간다():
    agents, backend = _Agents(), _Backend()

    with _client(agents, backend) as client:
        run_id = _submit(client)
        backend.wait_for("product_result")

    run = _run(backend.accepted(), run_id)
    assert _progress(run) == FIRST_ROUND + FINALIZATION
    result = run[-1]
    assert (result["eventType"], result["assessment"]["status"]) == ("product_result", "completed")
    assert _reviews(result) == {"ELECTRICAL": "COMPLETED"}


def test_Tool이_실패해도_진단은_끝까지_가고_결과에_그_분야가_미완료로_나간다():
    agents, backend = _Agents(failing={ToolName.ELECTRICAL}), _Backend()

    with _client(agents, backend) as client:
        run_id = _submit(client)
        backend.wait_for("product_result")

    run = _run(backend.accepted(), run_id)
    assert _progress(run) == FIRST_ROUND + FINALIZATION
    assert _reviews(run[-1]) == {"ELECTRICAL": "INCOMPLETE"}
    assert run[-1]["assessment"]["resultStatus"] == "RECHECK_REQUIRED"


def test_검증이_Tool을_더_요청하면_그_Tool만_재실행하고_두_분야_결과가_나간다():
    agents = _Agents(verifications=[VerificationStatus.TOOLS_REQUIRED, VerificationStatus.APPROVED])
    backend = _Backend()

    with _client(agents, backend) as client:
        run_id = _submit(client)
        backend.wait_for("product_result")

    run = _run(backend.accepted(), run_id)
    assert _progress(run) == FIRST_ROUND + RETRY_ROUND + FINALIZATION
    assert agents.executed == [ToolName.ELECTRICAL, ToolName.RADIO]
    assert _reviews(run[-1]) == {"ELECTRICAL": "COMPLETED", "RADIO": "COMPLETED"}


def test_답변이_필요하면_질문_콜백으로_멈추고_답변을_받으면_새_runId로_이어서_결과가_나간다():
    agents = _Agents(verifications=[VerificationStatus.USER_INPUT_REQUIRED, VerificationStatus.APPROVED])
    backend = _Backend()

    with _client(agents, backend) as client:
        run_id = _submit(client)
        waiting = backend.wait_for("product_awaiting_input")
        response = client.post(RESUME, json={
            "diagnosisId": "d-1", "productId": "p-1", "runId": run_id, "questionRound": 1,
            "answers": [{"questionKey": "r1_q1", "answerText": "3세 이상"}],
        })
        resumed_id = response.json()["data"]["runId"]
        backend.wait_for("product_result")

    assert _progress(_run(backend.accepted(), run_id)) == FIRST_ROUND + FINALIZATION
    assert (waiting["questionRound"], waiting["questions"]) == (1, [{
        "questionKey": "r1_q1", "questionOrder": 1,
        "questionText": "몇 세 이상이 쓰는 제품인가요?", "helpText": "어린이 제품인지 판단",
    }])
    assert response.status_code == 202 and resumed_id != run_id
    resumed = _run(backend.accepted(), resumed_id)
    assert _progress(resumed) == FIRST_ROUND + FINALIZATION
    assert resumed[-1]["eventType"] == "product_result"
    # 재진단은 이전 추출 결과를 그대로 씀
    assert len(agents.extracted) == 1


def test_입력_가드가_차단하면_파이프라인을_돌지_않고_검토_표시가_붙은_일반_실패로_끝난다():
    agents, backend = _Agents(guard=GuardOutcome.BLOCK), _Backend()

    with _client(agents, backend) as client:
        run_id = _submit(client)
        backend.wait_for("product_failed")

    run = _run(backend.accepted(), run_id)
    assert _progress(run) == [("extraction", "started", None)]
    assert run[-1]["error"] == {"code": "AI_PIPELINE_ERROR", "message": "진단 실행 중 오류가 발생했습니다.",
                                "retryable": False, "reviewFlag": "r1"}
    assert agents.extracted == []


def test_BE가_결과_콜백에_500을_주면_같은_이벤트를_다시_보내_한_번_받게_한다():
    failed = []

    def respond(event):
        # 첫 결과 콜백만 500
        if event["eventType"] == "product_result" and not failed:
            failed.append(event)
            return 500
        return 200

    agents, backend = _Agents(), _Backend(respond)

    with _client(agents, backend) as client:
        run_id = _submit(client)
        result = backend.wait_for("product_result")

    sent = [event for event, status in backend.received if event["eventType"] == "product_result"]
    assert [event["eventId"] for event in sent] == [failed[0]["eventId"]] * 2
    assert result == failed[0]
    assert _progress(_run(backend.accepted(), run_id)) == FIRST_ROUND + FINALIZATION
