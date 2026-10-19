"""진단 세션 상태 스키마의 기본값과 입력 검증을 확인한다."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.observability.context import ExecutionContext, RunType
from app.schemas.agent import ExtractionInput
from app.schemas.session import DiagnosisSession, SessionAnswer, SessionStatus

_SOURCE = ExtractionInput(product_id="p-1", text_blocks=["상품 설명"])


def _context() -> ExecutionContext:
    return ExecutionContext.start(product_id="p-1", run_type=RunType.PRODUCTION, diagnosis_id="d-1")


def test_새_세션은_접수_상태이고_단계와_결과가_없다():
    session = DiagnosisSession(context=_context(), source=_SOURCE)

    assert session.status is SessionStatus.ACCEPTED
    assert session.stage is None
    assert session.stage_started_at is None
    assert session.termination_reason is None
    assert session.result is None
    assert session.error_code is None
    assert session.retryable is None


def test_새_세션은_질문과_답변이_없다():
    session = DiagnosisSession(context=_context(), source=_SOURCE)

    assert (session.question_round, session.questions, session.answers) == (0, [], [])


def test_원래_입력_없이는_세션을_만들_수_없다():
    with pytest.raises(ValidationError):
        DiagnosisSession(context=_context())


@pytest.mark.parametrize("fields", [
    {"question_round": 0, "question_key": "battery_only", "answer_text": "네"},
    {"question_round": 1, "question_key": "", "answer_text": "네"},
    {"question_round": 1, "question_key": "battery_only", "answer_text": ""},
])
def test_답변은_회차_1_이상과_비어_있지_않은_키와_답을_요구한다(fields):
    with pytest.raises(ValidationError):
        SessionAnswer(**fields)


def test_접수_시각과_갱신_시각은_UTC로_채워진다():
    session = DiagnosisSession(context=_context(), source=_SOURCE)

    assert session.accepted_at.tzinfo is not None
    assert session.updated_at.tzinfo is not None


def test_시간대_없는_시각은_거부한다():
    # #171 §7.1 AwareDatetime
    with pytest.raises(ValidationError):
        DiagnosisSession(context=_context(), source=_SOURCE, updated_at=datetime(2026, 10, 7, 12, 0))


def test_실행_컨텍스트_없이는_세션을_만들_수_없다():
    with pytest.raises(ValidationError):
        DiagnosisSession()


def test_다른_시간대의_시각은_UTC로_바꿔_저장한다():
    # #171 §7.1 timezone-aware 입력의 UTC 정규화
    kst = timezone(timedelta(hours=9))

    session = DiagnosisSession(
        context=_context(),
        source=_SOURCE,
        stage_started_at=datetime(2026, 10, 8, 21, 0, tzinfo=kst),
        updated_at=datetime(2026, 10, 8, 21, 0, tzinfo=kst),
    )

    assert session.stage_started_at == datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    assert session.stage_started_at.utcoffset() == timedelta(0)
    assert session.updated_at.utcoffset() == timedelta(0)
