"""Sentry 설정: DSN이 없으면 끄고, 켜면 ERROR 로그·요청 중 잡지 않은 예외만 이벤트로 보낸다.

실제 Sentry로 보내지 않고 메모리 전송으로 받음.
"""

import json
import logging
import threading

import httpx
import pytest
import sentry_sdk
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app.domain.context import ExecutionContext, RunType
from app.observability.logs import run_log_context, set_run_field
from app.observability.sentry import configure_sentry

DSN = "https://public-key@o0.ingest.sentry.io/1"


class _MemoryTransport(Transport):
    """보낼 이벤트를 메모리에 모음."""

    events: list[dict] = []
    # 보낸 항목 종류 (로그 전송이 꺼졌는지 확인용)
    item_types: list[str] = []

    def capture_envelope(self, envelope):
        _MemoryTransport.item_types.extend(item.type for item in envelope.items)
        _MemoryTransport.events.extend(item.payload.json for item in envelope.items if item.type == "event")


@pytest.fixture
def events():
    """메모리 전송으로 Sentry를 켜고 보낸 이벤트를 돌려줌. 끝나면 끔."""
    _MemoryTransport.events = []
    _MemoryTransport.item_types = []
    assert configure_sentry(DSN, "test", transport=_MemoryTransport)
    yield _MemoryTransport.events
    sentry_sdk.init(dsn=None)


def _sent(events):
    sentry_sdk.flush()
    return [(event["level"], event["exception"]["values"][-1]["value"] if "exception" in event
             else event["logentry"]["message"]) for event in events]


def test_DSN이_없으면_켜지_않는다():
    assert configure_sentry("", "test") is False
    assert not sentry_sdk.get_client().is_active()


def test_ERROR_로그만_이벤트로_보내고_INFO·WARNING은_보내지_않는다(events, caplog):
    caplog.set_level(logging.INFO, logger="app")

    def session_thread():
        # 세션 스레드에서 잡아 로그로 남기는 실패 (진단 실행기와 같은 모양)
        try:
            raise ValueError("코드 오류")
        except ValueError:
            logging.getLogger("app.sessions").error("진단 실행 실패", exc_info=True)
        logging.getLogger("app.diagnosis.job").warning("진단 단계 실패 (예상한 실패)")
        logging.getLogger("app.sessions").info("진단 시작")

    thread = threading.Thread(target=session_thread)
    thread.start()
    thread.join()

    assert _sent(events) == [("error", "코드 오류")]
    assert events[0]["environment"] == "test"
    # 앞선 INFO·WARNING은 흐름 기록으로만
    assert all(crumb["level"] != "error" for crumb in events[0].get("breadcrumbs", {}).get("values", []))
    # 로그 전송은 안 함 (할당량)
    assert "log" not in _MemoryTransport.item_types


def test_요청_중_잡지_않은_예외는_보내고_HTTP_예외는_보내지_않으며_본문은_넣지_않는다(events):
    app = FastAPI()

    @app.post("/boom")
    def boom():
        raise RuntimeError("요청 처리 버그")

    @app.post("/conflict")
    def conflict():
        raise HTTPException(status_code=409, detail="진행 중인 상품")

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/boom", json={"textBlocks": ["상품 원문"]}).status_code == 500
        assert client.post("/conflict").status_code == 409

    assert _sent(events) == [("error", "요청 처리 버그")]
    # 본문 자리엔 설정으로 뺐다는 표시만
    assert "상품 원문" not in json.dumps(events[0], ensure_ascii=False)


def test_진단_실행_중_이벤트엔_로그와_같은_실행_정보를_태그로_붙인다(events):
    context = ExecutionContext(run_id="run-1", product_id="p-1", run_type=RunType.PRODUCTION, diagnosis_id="d-1")

    with run_log_context(context):
        set_run_field("stage", "tool_execution")
        logging.getLogger("app.diagnosis.job").error("Tool 실행 실패")
    logging.getLogger("app.main").error("세션 정리 실패")

    sentry_sdk.flush()
    in_run, outside = events
    assert {key: in_run["tags"][key] for key in ("diagnosis_id", "product_id", "run_id", "run_type", "stage")} == {
        "diagnosis_id": "d-1", "product_id": "p-1", "run_id": "run-1", "run_type": "production",
        "stage": "tool_execution"}
    assert "run_id" not in outside.get("tags", {})


def test_내부_인증_헤더·지역_변수는_보내지_않고_URL의_키는_가린다(events):
    # 이벤트엔 오류 위치 주변 소스 줄도 실림 → 비밀값은 소스에 한 덩어리로 안 나오게 이어 붙임
    key, token, dev_key, raw_text = ("SECRET" + suffix for suffix in ("-KEY", "-TOKEN", "-DEV", "-RAW-TEXT"))
    app = FastAPI()
    url = f"https://apis.data.go.kr/a?serviceKey={key}&x=1"

    @app.post("/boom")
    def boom():
        local_text = raw_text  # noqa: F841
        logging.getLogger("app.clients").info("호출 %s", url)
        logging.getLogger("app.clients").error("조회 실패 %s", url)
        raise RuntimeError(f"실패 {url}")

    TestClient(app, raise_server_exceptions=False).post(
        "/boom", headers={"X-Internal-Token": token, "X-Dev-Api-Key": dev_key})

    sentry_sdk.flush()
    sent = json.dumps(events, ensure_ascii=False)
    for secret in (key, token, dev_key, raw_text):
        assert secret not in sent
    assert "serviceKey=***" in sent


def test_외부_호출_흐름_기록의_쿼리와_로그_추가_값의_키도_가린다(events):
    key = "SECRET" + "-QUERY"
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    client.get(f"https://apis.data.go.kr/a?serviceKey={key}&x=1")
    client.get(f"https://www.law.go.kr/DRF/lawService.do?OC={key}&target=law")

    logging.getLogger("app.clients").error("조회 실패", extra={"url": f"https://a?serviceKey={key}"})

    sentry_sdk.flush()
    [event] = events
    assert key not in json.dumps(event, ensure_ascii=False)
    # 앞 테스트의 흐름 기록(쿼리 없는 요청 등)도 남아 있음 → 쿼리가 있는 외부 호출 기록만
    assert [crumb["data"]["http.query"] for crumb in event["breadcrumbs"]["values"]
            if crumb.get("data", {}).get("http.query")] == ["serviceKey=***&x=1", "OC=***&target=law"]
    assert event["extra"]["url"] == "https://a?serviceKey=***"
