"""진단 입력 → 상품 정보(Product) 추출 단계 (#432).

재진단이면 이전 추출 결과를 그대로 쓰고, URL만 있으면 수집해서 추출 입력을 만든다.
실패는 오류 코드·재시도 여부를 담은 AIServiceError로 던짐. 진단 함수(#320)는 이를 JobFailed로 옮기기만 하면 됨.
진행 알림(EXTRACTION)과 사용자 답변 전달은 진단 함수 몫.
"""

import logging
import time

import httpx
from openai import LengthFinishReasonError

from ..agents.base.errors import AgentError, ModelFailurePhase
from ..agents.image_triage.errors import ImageTriageFailedError
from ..domain.context import PipelineStage
from ..domain.errors import AIResponseCode, AIServiceError
from ..schemas.agent import ExtractionInput
from ..schemas.product import Product
from ..schemas.session import DiagnosisInput
from .errors import UnsupportedSiteError
from .runner import ExtractionStage
from .url_source import UrlSourceBuilder

logger = logging.getLogger(__name__)


class ExtractionStep:
    """진단 입력 하나를 상품 정보로 만든다.

    Args:
        extractor: 추출 에이전트.
        url_builder: URL만 있는 입력을 추출 입력으로 만드는 수집기.
    """

    def __init__(self, extractor: ExtractionStage, url_builder: UrlSourceBuilder) -> None:
        self._extractor = extractor
        self._url_builder = url_builder

    def run(self, job_input: DiagnosisInput) -> Product:
        """진단 입력을 상품 정보로 만든다.

        Args:
            job_input: 진단 함수가 받은 실행 입력.

        Returns:
            Product: 추출 결과. 재진단이면 이전 실행의 추출 결과.

        Raises:
            AIServiceError: 수집·추출 실패. response_code·retryable로 원인을 구분.
        """
        # 답변은 추출 결과에 합치지 않음. 질문 키가 정해지기 전까지 이전 추출 결과를 그대로 씀 (#412)
        if job_input.previous is not None:
            return job_input.previous.product
        source = job_input.source
        if not source.text_blocks and not source.image_urls:
            source = self._collect(source)
        try:
            return self._extractor.run(source)
        except AgentError as exc:
            raise _failure(AIResponseCode.PIPELINE_ERROR, retryable=_retryable(exc)) from exc

    def _collect(self, source: ExtractionInput) -> ExtractionInput:
        """URL로 페이지를 수집해 추출 입력을 만든다. 수집 시간은 모델 호출 시간과 나눠 로그로 남김 (#410)."""
        started = time.perf_counter()
        try:
            collected = self._url_builder.build(source.source_url, product_id=source.product_id).extraction_input
        except UnsupportedSiteError as exc:
            raise _failure(AIResponseCode.UNSUPPORTED_SITE, retryable=False) from exc
        except httpx.HTTPError as exc:
            raise _failure(AIResponseCode.SOURCE_FETCH_FAILED, retryable=True) from exc
        except ImageTriageFailedError as exc:
            raise _failure(AIResponseCode.PIPELINE_ERROR, retryable=True) from exc
        logger.info("URL 수집 완료 (product_id=%s, 글 %d개, 이미지 %d장, %dms)", source.product_id,
                    len(collected.text_blocks), len(collected.image_urls), (time.perf_counter() - started) * 1000)
        if not collected.text_blocks and not collected.image_urls:
            raise _failure(AIResponseCode.EMPTY_SOURCE, retryable=False)
        return collected


def _retryable(exc: AgentError) -> bool:
    """추출 실패를 같은 입력으로 다시 해 볼 만한지.

    응답을 받지 못한 경우와, 같은 내용을 반복하다 출력 한도에 닿은 경우만 재시도 가능.
    그 밖의 출력 해석 실패는 같은 입력으로 다시 해도 반복될 수 있음.
    """
    if isinstance(exc.__cause__, LengthFinishReasonError):
        return True
    phase = exc.meta.failure_phase if exc.meta is not None else None
    return phase == ModelFailurePhase.CALL


def _failure(code: AIResponseCode, *, retryable: bool) -> AIServiceError:
    return AIServiceError(response_code=code.value, stage=PipelineStage.EXTRACTION, retryable=retryable)
