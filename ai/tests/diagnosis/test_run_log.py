"""진단 실행 로그 hook: 재실행 회차 로그 필드, Tool 실패 원인 로그."""

import pytest

from app.clients.errors import ClientError
from app.diagnosis.run_log import log_tool_failure, mark_retry_round
from app.domain.context import ExecutionContext, RunType
from app.observability.logs import current_run_fields, run_log_context
from app.schemas.schemas import ToolName
from app.tools.customs import CustomsToolError

CONTEXT = ExecutionContext(run_id="run-1", product_id="p-1", run_type=RunType.TEST)


def _raise(error):
    def call():
        raise error

    return call


@pytest.mark.parametrize(("error", "level", "traceback"), [
    (ClientError("응답 없음 https://apis.data.go.kr/x?serviceKey=SECRET&page=1"), "WARNING", False),
    (RuntimeError("버그"), "ERROR", True),
])
def test_Tool_실패는_원인을_남기고_예상한_오류는_위치_없이_코드_오류는_위치까지_남긴다(caplog, error, level, traceback):
    with pytest.raises(type(error)):
        log_tool_failure(ToolName.RADIO, _raise(error))

    [record] = [r for r in caplog.records if r.name == "app.diagnosis.run_log"]
    assert record.levelname == level
    assert record.getMessage().startswith(f"Tool 실행 실패 {ToolName.RADIO}: {type(error).__name__}: ")
    assert "SECRET" not in record.getMessage()
    assert (record.exc_info is not None) is traceback


def test_Tool_실패_로그에_감싼_원인까지_남긴다(caplog):
    # 통관 Tool은 요건 조회의 모든 예외를 "세관장확인 요건 조회에 실패했습니다"로 감싼다.
    # 바깥 문장만 남으면 서버에서 실제 원인(시간 초과·연결 실패 등)을 알 수 없다.
    try:
        try:
            raise ClientError("연결 실패 https://apis.data.go.kr/x?serviceKey=SECRET")
        except ClientError as cause:
            raise CustomsToolError("세관장확인 요건 조회에 실패했습니다.") from cause
    except CustomsToolError as wrapped:
        error = wrapped

    with pytest.raises(CustomsToolError):
        log_tool_failure(ToolName.CUSTOMS, _raise(error))

    [record] = [r for r in caplog.records if r.name == "app.diagnosis.run_log"]
    message = record.getMessage()
    assert message.startswith(f"Tool 실행 실패 {ToolName.CUSTOMS}: CustomsToolError: 세관장확인 요건 조회에 실패했습니다.")
    assert "← ClientError: 연결 실패" in message
    assert "SECRET" not in message


def test_Tool이_성공하면_결과를_그대로_돌려주고_로그를_남기지_않는다(caplog):
    assert log_tool_failure(ToolName.RADIO, lambda: "결과") == "결과"
    assert [r for r in caplog.records if r.name == "app.diagnosis.run_log"] == []


def test_재실행_회차부터_단계_안_로그_줄에_회차가_붙는다():
    seen = []

    with run_log_context(CONTEXT):
        for stage, retry_round in [("verification", 0), ("tool_execution", 1), ("aggregation", 1)]:
            mark_retry_round(stage, retry_round, lambda: seen.append(current_run_fields().get("retry_round")))

    assert seen == [None, "1", "1"]
