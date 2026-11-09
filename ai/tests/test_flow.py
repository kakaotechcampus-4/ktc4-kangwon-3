"""HTTP 접수부터 BE 콜백까지 실제 진단 흐름을 확인한다.

세션·진단 함수(job)·파이프라인 순서(runner)·Tool 실행·집계·질문 만들기·콜백 발신함은 실제 코드.
모델·외부 호출 자리(추출·Tool 선택·Tool·검증 에이전트, 입력 가드 판정)만 가짜, BE는 httpx.MockTransport.
콜백은 BE 계약 키(eventType·runId·sequence·단계·질문·오류·결과 요약)만 비교.
"""

import pytest
from fastapi.testclient import TestClient

from app.agents.input_guard import GuardOutcome, GuardVerdict
from app.diagnosis import build_job, build_questions, guarded
from app.diagnosis.assembly import PipelineParts
from app.pipeline.aggregator import ResultAggregator
from app.pipeline.extraction_step import ExtractionStep
from app.schemas.agent import ToolSelectionItem, ToolSelectionResponse
from app.schemas.product import Product
from app.schemas.schemas import FollowUpQuestion, ToolName, ToolResult, ToolStatus, VerificationResult, VerificationStatus
from tests.app_harness import TOKEN, FakeBackend, app_env, client, fake_parts

pytestmark = pytest.mark.integration

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
def _env(monkeypatch):
    yield from app_env(monkeypatch)


class _Agents:
    """모델·외부 호출 자리 가짜. 고를 Tool·실패할 Tool·검증 회차별 상태·가드 판정을 정해 두고, 부른 기록을 남김."""

    def __init__(self, *, failing=(), verifications=(VerificationStatus.APPROVED,), guard=GuardOutcome.PASS):
        self.failing = set(failing)
        self.verifications = list(verifications)
        self.guard = guard
        self.extracted: list = []
        self.executed: list[ToolName] = []
        # Tool이 받은 상품 정보 (실행 순서대로)
        self.received: list[Product] = []

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
                agents.received.append(product)
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


def _client(agents: _Agents, backend: FakeBackend) -> TestClient:
    return client(fake_parts(backend, pipeline_job=agents.job()), headers={"X-Internal-Token": TOKEN})


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
    agents, backend = _Agents(), FakeBackend()

    with _client(agents, backend) as client:
        run_id = _submit(client)
        backend.wait_for("product_result")

    run = _run(backend.accepted(), run_id)
    assert _progress(run) == FIRST_ROUND + FINALIZATION
    result = run[-1]
    assert (result["eventType"], result["assessment"]["status"]) == ("product_result", "completed")
    assert _reviews(result) == {"ELECTRICAL": "COMPLETED"}


def test_Tool이_실패해도_진단은_끝까지_가고_결과에_그_분야가_미완료로_나간다():
    agents, backend = _Agents(failing={ToolName.ELECTRICAL}), FakeBackend()

    with _client(agents, backend) as client:
        run_id = _submit(client)
        backend.wait_for("product_result")

    run = _run(backend.accepted(), run_id)
    assert _progress(run) == FIRST_ROUND + FINALIZATION
    assert _reviews(run[-1]) == {"ELECTRICAL": "INCOMPLETE"}
    assert run[-1]["assessment"]["resultStatus"] == "RECHECK_REQUIRED"


def test_검증이_Tool을_더_요청하면_그_Tool만_재실행하고_두_분야_결과가_나간다():
    agents = _Agents(verifications=[VerificationStatus.TOOLS_REQUIRED, VerificationStatus.APPROVED])
    backend = FakeBackend()

    with _client(agents, backend) as client:
        run_id = _submit(client)
        backend.wait_for("product_result")

    run = _run(backend.accepted(), run_id)
    assert _progress(run) == FIRST_ROUND + RETRY_ROUND + FINALIZATION
    assert agents.executed == [ToolName.ELECTRICAL, ToolName.RADIO]
    assert _reviews(run[-1]) == {"ELECTRICAL": "COMPLETED", "RADIO": "COMPLETED"}


def test_답변이_필요하면_질문_콜백으로_멈추고_답변을_받으면_새_runId로_이어서_결과가_나간다():
    agents = _Agents(verifications=[VerificationStatus.USER_INPUT_REQUIRED, VerificationStatus.APPROVED])
    backend = FakeBackend()

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
    # 재진단 Tool은 답변 줄이 붙은 상품 정보를 받음 (첫 실행엔 없음)
    first, resumed_product = agents.received
    assert first.listing_text == []
    assert resumed_product.listing_text == ["[사용자 답변] 몇 세 이상이 쓰는 제품인가요? → 3세 이상"]


def test_입력_가드가_차단하면_파이프라인을_돌지_않고_검토_표시가_붙은_일반_실패로_끝난다():
    agents, backend = _Agents(guard=GuardOutcome.BLOCK), FakeBackend()

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

    agents, backend = _Agents(), FakeBackend(respond)

    with _client(agents, backend) as client:
        run_id = _submit(client)
        result = backend.wait_for("product_result")

    sent = [event for event in backend.events if event["eventType"] == "product_result"]
    assert [event["eventId"] for event in sent] == [failed[0]["eventId"]] * 2
    assert result == failed[0]
    assert _progress(_run(backend.accepted(), run_id)) == FIRST_ROUND + FINALIZATION
