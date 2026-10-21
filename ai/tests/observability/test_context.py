"""공통 실행 컨텍스트의 생성·회차 규칙을 확인한다 (#171 §2.2)."""

import pytest
from pydantic import ValidationError

from app.observability.context import ExecutionContext, RunType


def _context() -> ExecutionContext:
    return ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION, diagnosis_id="d-1")


def test_시작하면_run_id를_만들고_회차는_0이다():
    context = _context()

    assert context.run_id
    assert context.retry_round == 0


def test_시작할_때마다_다른_run_id를_만든다():
    assert _context().run_id != _context().run_id


def test_다음_회차는_회차만_올리고_식별_정보는_유지한다():
    context = _context()

    retry = context.next_round()

    assert retry.retry_round == 1
    assert (retry.run_id, retry.product_id, retry.diagnosis_id, retry.run_type) == (
        context.run_id, context.product_id, context.diagnosis_id, context.run_type,
    )
    assert context.retry_round == 0


def test_회차는_0에서_1_2로_이어지고_이전_컨텍스트는_그대로다():
    # #171 §9 M2: 0→1→2 retry_round, 부모 context 불변
    first = _context()
    second = first.next_round()

    third = second.next_round()

    assert (first.retry_round, second.retry_round, third.retry_round) == (0, 1, 2)
    assert third.run_id == first.run_id


def test_컨텍스트는_변경할_수_없다():
    with pytest.raises(ValidationError):
        _context().retry_round = 1


@pytest.mark.parametrize("retry_round", [True, -1])
def test_회차는_0_이상_정수만_허용한다(retry_round):
    with pytest.raises(ValidationError):
        ExecutionContext(run_id="r-1", product_id="p-1", run_type=RunType.TEST, retry_round=retry_round)


def test_단독_평가는_진단서_ID_없이_만들_수_있다():
    context = ExecutionContext.start(product_id="fixture-1", run_type=RunType.EVALUATION)

    assert context.diagnosis_id is None
