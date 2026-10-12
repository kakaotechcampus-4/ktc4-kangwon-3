"""공통 응답 코드와 AIServiceError의 계약(#171 §6.1)을 확인한다."""

import pytest

from app.errors import AIResponseCode, AIServiceError
from app.observability.context import PipelineStage
from app.schemas.response import DiagnosisConflict


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
