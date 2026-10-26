"""부하 테스트용 Mock AI 서버.

실제 AI 서버의 BE 계약만 흉내 낸다.
    - POST /api/ai/v1/diagnose/content, /resume → 바로 202 접수(상품별 runId)
    - 접수한 상품마다 백그라운드에서 진행 콜백을 보내고 결과·질문·실패 콜백 하나로 끝냄
      (순서는 ai/app/callbacks/events.py와 같게: 앞 단계 completed + 새 단계 started, Tool 실행 단계 안에서 Tool 진행)
    - 큐나 동시 처리 제한 없이 모두 받는다.
콜백 재시도는 실제 AI(ai/app/callbacks/http.py)처럼 5xx·타임아웃·409 COMMON-009만 지수 백오프로 최대 5회.
"""
import asyncio
import logging
import os
import random
import time
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

BE_BASE_URL = os.environ.get("BE_BASE_URL", "http://perf-app:8080").rstrip("/")
INTERNAL_API_TOKEN = os.environ["INTERNAL_API_TOKEN"]

DURATION_MIN_S = float(os.environ.get("MOCK_DURATION_MIN_S", "60"))
DURATION_MAX_S = float(os.environ.get("MOCK_DURATION_MAX_S", "120"))
FIRST_CALLBACK_DELAY_S = float(os.environ.get("MOCK_FIRST_CALLBACK_DELAY_MS", "500")) / 1000
ACCEPT_LATENCY_S = float(os.environ.get("MOCK_ACCEPT_LATENCY_MS", "0")) / 1000
QUESTION_RATIO = float(os.environ.get("MOCK_QUESTION_RATIO", "0.2"))
FAIL_RATIO = float(os.environ.get("MOCK_FAIL_RATIO", "0"))
REJECT_429_RATIO = float(os.environ.get("MOCK_429_RATIO", "0"))

CALLBACK_TIMEOUT_S = 5.0
MAX_RETRIES = 5
BACKOFF_BASE_S = 1.0
BACKOFF_MAX_S = 30.0
# BE가 202의 runId를 아직 저장하지 않았을 때 주는 코드. 실제 AI도 재시도한다.
RUN_NOT_ASSIGNED_CODE = "COMMON-009"

STAGES = ["extraction", "selection", "tool_execution", "aggregation", "verification", "finalization"]
# 질문으로 끝나는 실행은 앞 단계까지만, 재진단 실행은 Tool 실행부터 이어서 한다.
QUESTION_STAGES = STAGES[:2]
RESUME_STAGES = STAGES[2:]
TOOLS = ["CUSTOMS", "CHILDREN", "ELECTRICAL", "RADIO", "FOOD_DRUG", "LABEL_AD"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("mock-ai")
# 요청마다 INFO 로그를 남겨 부하 중 로그가 넘치지 않게
logging.getLogger("httpx").setLevel(logging.WARNING)

ACCEPTED = Counter("mock_ai_accepted_total", "접수한 요청 수", ["endpoint", "result"])
CALLBACKS = Counter("mock_ai_callbacks_total", "콜백 최종 결과", ["event_type", "outcome"])
CALLBACK_ATTEMPTS = Counter("mock_ai_callback_attempts_total", "콜백 시도별 응답", ["status"])
CALLBACK_RETRIES = Counter("mock_ai_callback_retries_total", "콜백 재시도 수", ["reason"])
CALLBACK_LATENCY = Histogram(
    "mock_ai_callback_duration_seconds", "콜백 1회 응답 시간",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
RUN_DURATION = Histogram(
    "mock_ai_run_duration_seconds", "접수부터 마지막 콜백 전송까지", ["terminal"],
    buckets=(5, 10, 30, 60, 90, 120, 150, 180, 240, 300, 600),
)
RUNS_INFLIGHT = Gauge("mock_ai_runs_inflight", "콜백을 보내는 중인 실행 수")

app = FastAPI(title="mock-ai")
client: httpx.AsyncClient | None = None
# 백그라운드 작업이 GC되지 않게 참조를 잡아 둔다.
tasks: set[asyncio.Task] = set()


@app.on_event("startup")
async def startup() -> None:
    global client
    # 콜백이 몰릴 때 클라이언트 풀에서 줄 서지 않도록 연결 수 제한을 두지 않는다.
    client = httpx.AsyncClient(
        timeout=CALLBACK_TIMEOUT_S,
        limits=httpx.Limits(max_connections=None, max_keepalive_connections=200),
        headers={"X-Internal-Token": INTERNAL_API_TOKEN},
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    if client is not None:
        await client.aclose()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "inflight": len(tasks)}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/ai/v1/diagnose/content")
async def diagnose(request: Request) -> JSONResponse:
    body = await request.json()
    if rejected := await _maybe_reject("content"):
        return rejected

    diagnosis_id = body["diagnosisId"]
    accepted = []
    for product in body.get("products", []):
        run_id = str(uuid4())
        ask_question = random.random() < QUESTION_RATIO
        stages = QUESTION_STAGES if ask_question else STAGES
        _spawn(_run(diagnosis_id, product["productId"], run_id, stages, ask_question))
        accepted.append({"productId": product["productId"], "runId": run_id, "status": "accepted"})

    ACCEPTED.labels("content", "accepted").inc()
    return _accepted({"diagnosisId": diagnosis_id, "products": accepted})


@app.post("/api/ai/v1/diagnose/resume")
async def resume(request: Request) -> JSONResponse:
    body = await request.json()
    if rejected := await _maybe_reject("resume"):
        return rejected

    run_id = str(uuid4())
    _spawn(_run(body["diagnosisId"], body["productId"], run_id, RESUME_STAGES, False))
    ACCEPTED.labels("resume", "accepted").inc()
    return _accepted({"productId": body["productId"], "runId": run_id, "status": "accepted"})


async def _maybe_reject(endpoint: str) -> JSONResponse | None:
    if ACCEPT_LATENCY_S > 0:
        await asyncio.sleep(ACCEPT_LATENCY_S)
    if random.random() < REJECT_429_RATIO:
        ACCEPTED.labels(endpoint, "rejected_429").inc()
        return JSONResponse(status_code=429, content={"code": "AI_QUEUE_FULL", "message": "대기열이 가득 찼습니다.", "data": None})
    return None


def _accepted(data: dict) -> JSONResponse:
    return JSONResponse(status_code=202, content={"code": "OK", "message": "진단 요청이 접수되었습니다.", "data": data})


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    tasks.add(task)
    task.add_done_callback(tasks.discard)


async def _run(diagnosis_id: str, product_id: str, run_id: str, stages: list[str], ask_question: bool) -> None:
    """실행 하나의 콜백을 순서대로 보낸다. 같은 실행의 콜백은 앞 콜백이 끝난 뒤에 보낸다(BE가 sequence로 순서를 본다)."""
    started_at = time.monotonic()
    RUNS_INFLIGHT.inc()
    try:
        tools = random.sample(TOOLS, k=random.randint(1, 2))
        steps = _progress_steps(stages, tools)
        terminal = "awaiting_input" if ask_question else ("failed" if random.random() < FAIL_RATIO else "result")

        # 전체 처리 시간을 단계 사이에 고르게 나눈다. 질문 실행은 전체의 30%만 쓰고 나머지는 재진단 실행이 쓴다.
        total = random.uniform(DURATION_MIN_S, DURATION_MAX_S)
        if ask_question:
            total *= 0.3
        elif stages is RESUME_STAGES:
            total *= 0.7
        interval = total / (len(steps) + 1)

        sequence = 0

        def base() -> dict:
            nonlocal sequence
            sequence += 1
            return {"eventId": str(uuid4()), "diagnosisId": diagnosis_id, "productId": product_id,
                    "runId": run_id, "sequence": sequence}

        await asyncio.sleep(max(FIRST_CALLBACK_DELAY_S, interval))
        for stage, stage_status, tool_name in steps:
            event = {**base(), "eventType": "product_progress", "stage": stage, "stageStatus": stage_status}
            if tool_name is not None:
                event["toolName"] = tool_name
            await _send(event)
            await asyncio.sleep(interval)

        last_stage = stages[-1]
        if terminal == "awaiting_input":
            event = {**base(), "eventType": "product_awaiting_input", "questionRound": 1, "questions": _questions()}
        elif terminal == "failed":
            event = {**base(), "eventType": "product_failed", "stage": last_stage,
                     "error": {"code": "AI_PIPELINE_ERROR", "message": "진단 중 오류가 발생했습니다.", "retryable": True}}
        else:
            event = {**base(), "eventType": "product_result", "assessment": _assessment(tools)}
        await _send(event)
        RUN_DURATION.labels(terminal).observe(time.monotonic() - started_at)
    except Exception:
        logger.exception("실행 실패 diagnosisId=%s productId=%s runId=%s", diagnosis_id, product_id, run_id)
    finally:
        RUNS_INFLIGHT.dec()


def _progress_steps(stages: list[str], tools: list[str]) -> list[tuple[str, str, str | None]]:
    """(stage, stageStatus, toolName) 목록. 앞 단계 completed 뒤에 새 단계 started, Tool 실행 단계 안에서 Tool별 started/completed."""
    steps: list[tuple[str, str, str | None]] = []
    previous = None
    for stage in stages:
        if previous is not None:
            steps.append((previous, "completed", None))
        steps.append((stage, "started", None))
        if stage == "tool_execution":
            for tool in tools:
                steps.append((stage, "started", tool))
                steps.append((stage, "completed", tool))
        previous = stage
    return steps


async def _send(event: dict) -> None:
    url = f"{BE_BASE_URL}/internal/v1/ai/products/{event['productId']}"
    event_type = event["eventType"]
    for attempt in range(MAX_RETRIES + 1):
        retry_reason = None
        started_at = time.monotonic()
        try:
            response = await client.post(url, json=event)
            CALLBACK_LATENCY.observe(time.monotonic() - started_at)
            CALLBACK_ATTEMPTS.labels(str(response.status_code)).inc()
            if response.is_success:
                CALLBACKS.labels(event_type, "ok").inc()
                return
            if response.status_code >= 500:
                retry_reason = "5xx"
            elif response.status_code == 409 and _code(response) == RUN_NOT_ASSIGNED_CODE:
                retry_reason = "run_not_assigned"
            else:
                logger.warning("콜백 거절 status=%s body=%s event=%s", response.status_code, response.text[:300], event_type)
                CALLBACKS.labels(event_type, f"rejected_{response.status_code}").inc()
                return
        except httpx.TimeoutException:
            CALLBACK_ATTEMPTS.labels("timeout").inc()
            retry_reason = "timeout"
        except httpx.TransportError:
            CALLBACK_ATTEMPTS.labels("connect_error").inc()
            retry_reason = "connect_error"

        if attempt == MAX_RETRIES:
            break
        CALLBACK_RETRIES.labels(retry_reason).inc()
        delay = min(BACKOFF_BASE_S * (2 ** attempt), BACKOFF_MAX_S)
        await asyncio.sleep(delay * random.uniform(0.5, 1.0))

    logger.warning("콜백 재시도 소진 event=%s productId=%s", event_type, event["productId"])
    CALLBACKS.labels(event_type, "gave_up").inc()


def _code(response: httpx.Response) -> str | None:
    try:
        return response.json().get("code")
    except ValueError:
        return None


def _questions() -> list[dict]:
    return [
        {"questionKey": "battery_included", "questionOrder": 1,
         "questionText": "제품에 배터리가 포함되어 있나요?", "helpText": "내장·교체형 모두 포함입니다."},
        {"questionKey": "target_age", "questionOrder": 2,
         "questionText": "사용 대상 연령이 어떻게 되나요?", "helpText": None},
    ]


def _assessment(tools: list[str]) -> dict:
    certification_required = random.random() < 0.5
    return {
        "status": "COMPLETED",
        "resultStatus": "DIRECT_IMPORT_CERTIFICATION_REQUIRED" if certification_required else "PURCHASING_AGENT_ALLOWED",
        "summary": "부하 테스트용 진단 결과입니다. 분야별 검토 결과를 확인하세요.",
        "toolReviews": [_tool_review(tool, certification_required) for tool in tools],
        "requiredActions": ["KC 인증 여부를 판매자에게 확인하세요."] if certification_required else [],
        "notices": [],
    }


def _tool_review(tool: str, certification_required: bool) -> dict:
    return {
        "toolName": tool,
        "status": "COMPLETED",
        "message": None,
        "findings": [{
            "subject": f"{tool} 검토 항목",
            "determination": "REQUIRED" if certification_required else "NOT_REQUIRED",
            "riskLevel": "MEDIUM" if certification_required else "LOW",
            "summary": "부하 테스트용 판단 요약입니다.",
            "rationale": "부하 테스트용 판단 근거입니다. 실제 법령 해석이 아닙니다.",
            "legalSources": [{
                "sourceName": "국가법령정보센터",
                "lawName": "전기용품 및 생활용품 안전관리법",
                "article": "제5조",
                "quotedText": "부하 테스트용 인용문입니다.",
                "sourceUrl": "https://www.law.go.kr",
                "effectiveDate": "2026-01-01",
            }],
        }],
    }
