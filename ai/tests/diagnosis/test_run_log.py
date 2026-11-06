"""진단 실행 로그 hook."""

from app.diagnosis.run_log import mark_retry_round
from app.domain.context import ExecutionContext, RunType
from app.observability.logs import current_run_fields, run_log_context

CONTEXT = ExecutionContext(run_id="run-1", product_id="p-1", run_type=RunType.TEST)


def test_재실행_회차부터_단계_안_로그_줄에_회차가_붙는다():
    seen = []

    with run_log_context(CONTEXT):
        for stage, retry_round in [("verification", 0), ("tool_execution", 1), ("aggregation", 1)]:
            mark_retry_round(stage, retry_round, lambda: seen.append(current_run_fields().get("retry_round")))

    assert seen == [None, "1", "1"]
