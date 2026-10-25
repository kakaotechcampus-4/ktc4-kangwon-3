"""공통 예외 뿌리(AIError)·응답 코드·AIServiceError의 계약(#171 §6.1)을 확인한다."""

import pytest

from app.agents.base import AgentError, MissingParsedOutput
from app.agents.extraction import ExtractionFailedError
from app.agents.image_triage import ImageTriageFailedError
from app.agents.selection import SelectionFailedError
from app.agents.verification import VerificationError
from app.callbacks.errors import CallbackTransportError
from app.clients.errors import ClientError
from app.clients.marketplace.errors import BlockedUrlError, PageTooLargeError
from app.config.errors import ConfigError
from app.domain.context import PipelineStage
from app.domain.errors import AIError, AIResponseCode, AIServiceError
from app.eval.errors import InputsMismatch, RawFixtureMissing
from app.pipeline.errors import UnsupportedSiteError
from app.repositories.errors import DatabaseNotConfiguredError
from app.schemas.response import DiagnosisConflict
from app.sessions.errors import (
    InvalidTransitionError,
    QueueFullError,
    ResumeConflictError,
    SessionConflictError,
    SessionError,
    SessionNotFoundError,
    UnansweredQuestionError,
    UnknownQuestionKeyError,
    UnsupportedRunTypeError,
)

# (예외, 원래 내장 부모). 원래 부모도 유지해야 기존 except가 계속 잡음
SERVICE_ERRORS = [
    (AIServiceError, RuntimeError),
    (ConfigError, RuntimeError),
    (DatabaseNotConfiguredError, RuntimeError),
    (AgentError, RuntimeError),
    (MissingParsedOutput, RuntimeError),
    (ExtractionFailedError, RuntimeError),
    (SelectionFailedError, RuntimeError),
    (VerificationError, RuntimeError),
    (ImageTriageFailedError, RuntimeError),
    (BlockedUrlError, ValueError),
    (PageTooLargeError, ValueError),
    (QueueFullError, RuntimeError),
    (SessionConflictError, RuntimeError),
    (SessionNotFoundError, LookupError),
    (ResumeConflictError, RuntimeError),
    (UnknownQuestionKeyError, ValueError),
    (UnansweredQuestionError, ValueError),
    (InvalidTransitionError, ValueError),
    (UnsupportedRunTypeError, LookupError),
    (CallbackTransportError, RuntimeError),
    (UnsupportedSiteError, ValueError),
]


@pytest.mark.parametrize(("error", "builtin"), SERVICE_ERRORS, ids=lambda value: value.__name__)
def test_서비스_예외는_AIError이면서_원래_내장_예외로도_잡힌다(error, builtin):
    assert issubclass(error, AIError)
    assert issubclass(error, builtin)


def test_분야별_부모로_묶인다():
    assert issubclass(BlockedUrlError, ClientError) and issubclass(PageTooLargeError, ClientError)
    assert all(issubclass(error, SessionError) for error in (
        QueueFullError, SessionConflictError, SessionNotFoundError, ResumeConflictError,
        UnknownQuestionKeyError, UnansweredQuestionError, InvalidTransitionError, UnsupportedRunTypeError,
    ))


def test_평가_예외는_AIError가_아니다():
    # 평가를 돌리는 사람이 보는 오류라 서비스 예외 집계에 섞지 않음
    assert not issubclass(RawFixtureMissing, AIError)
    assert not issubclass(InputsMismatch, AIError)


def test_응답_코드_문자열은_서로_겹치지_않는다():
    codes = [member.value.code for member in AIResponseCode]

    assert len(codes) == len(set(codes))
    assert all(code.startswith("AI_") for code in codes)


def test_AIServiceError는_RuntimeError로도_잡힌다():
    with pytest.raises(RuntimeError):
        raise AIServiceError(response_code=AIResponseCode.QUEUE_FULL.value)


def test_예외_메시지는_공개_문구와_같다():
    error = AIServiceError(response_code=AIResponseCode.SESSION_CONFLICT.value)

    assert str(error) == "이미 진행 중인 상품이 있습니다."


def test_기본값은_단계_없음_재시도_불가_부분_결과와_data_없음():
    error = AIServiceError(response_code=AIResponseCode.INTERNAL_ERROR.value)

    assert (error.stage, error.retryable, error.partial_result, error.data) == (None, False, None, None)


def test_단계_재시도_부분_결과_data를_그대로_보관한다():
    conflict = DiagnosisConflict(conflict_product_ids=["p-1"])

    error = AIServiceError(
        response_code=AIResponseCode.PIPELINE_ERROR.value,
        stage=PipelineStage.EXTRACTION,
        retryable=True,
        partial_result={"step": 1},
        data=conflict,
    )

    assert error.response_code.code == "AI_PIPELINE_ERROR"
    assert (error.stage, error.retryable, error.partial_result, error.data) == (
        PipelineStage.EXTRACTION, True, {"step": 1}, conflict,
    )


def test_원인_예외를_보존하고_공개_메시지에는_넣지_않는다():
    with pytest.raises(AIServiceError) as caught:
        try:
            raise TimeoutError("gateway 10.0.0.1 응답 없음")
        except TimeoutError as exc:
            raise AIServiceError(response_code=AIResponseCode.TIMEOUT.value, retryable=True) from exc

    assert isinstance(caught.value.__cause__, TimeoutError)
    assert "10.0.0.1" not in str(caught.value)
