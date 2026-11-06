"""파이프라인 단계 자리에 넣는 진단 단계 어댑터. 단계 고유 업무 로직만 둠 (진행 알림·trace 등은 hook)."""

import logging

from ..agents.verification import VerificationError
from ..pipeline.extraction_step import ExtractionStep
from ..pipeline.runner import VerificationStage
from ..schemas.agent import ExtractionInput
from ..schemas.product import Product
from ..schemas.schemas import DraftAssessment, VerificationResult, VerificationStatus
from ..schemas.session import DiagnosisInput
from .answers import with_answers
from .run_log import error_text

logger = logging.getLogger(__name__)


class JobInputExtraction:
    """추출 자리. 파이프라인이 넘기는 원래 입력 대신 실행 입력 전체로 추출 단계를 부름.

    재진단이면 이전 추출 결과에 이번 회차 답변을 붙여 선택 단계부터 다시 돎.
    다시 실행에서 저장한 추출 결과를 쓰면 이 자리는 안 불림 (저장한 결과엔 답변이 이미 붙어 있음).
    """

    def __init__(self, step: ExtractionStep, job_input: DiagnosisInput) -> None:
        """
        Args:
            step: 추출 단계.
            job_input: 이번 실행 입력.
        """
        self._step = step
        self._job_input = job_input

    def run(self, source: ExtractionInput) -> Product:
        """실행 입력으로 추출하고 이번 회차 답변을 붙인다.

        Args:
            source: 파이프라인이 넘기는 원래 입력. 쓰지 않음 (실행 입력에 들어 있음).

        Returns:
            Product: 답변을 붙인 상품 정보.
        """
        return with_answers(self._step.run(self._job_input), self._job_input)


class RulesFallbackVerification:
    """검증 자리. 검증 모델 검토가 실패해도 규칙 검사 결과가 있으면 그 결과로 진행.

    규칙 결과도 없으면 검증 실패를 그대로 올림 (진단 함수가 재시도 가능 실패로 바꿈).
    """

    def __init__(self, verifier: VerificationStage) -> None:
        """
        Args:
            verifier: 검증 단계.
        """
        self._verifier = verifier

    def run(self, draft: DraftAssessment) -> VerificationResult:
        """검증하고, 모델 검토가 실패하면 규칙 검사 결과로 대신한다.

        Args:
            draft: 종합 초안.

        Returns:
            VerificationResult: 검증 결과. 모델 검토 실패면 규칙 검사 결과 (통과는 재확인 필요로 바꿈).

        Raises:
            VerificationError: 규칙 검사 결과도 없는 검증 실패.
        """
        try:
            return self._verifier.run(draft)
        except VerificationError as exc:
            if not isinstance(exc.partial_result, VerificationResult):
                raise
            # 검토 ID 실수·모델 호출 실패. Tool 판단과 규칙 검사 결과는 버리지 않고 진행
            verification = _rules_only(exc.partial_result)
            logger.warning("검증 모델 검토 실패, 규칙 검사 결과로 진행 (status=%s): %s",
                           verification.status.value, error_text(exc))
            return verification


def _rules_only(rules: VerificationResult) -> VerificationResult:
    """모델 검토 없이 규칙 검사 결과만 남은 검증 결과. 모델 검토를 못 했으니 통과는 재확인 필요로 바꿈.

    Tool 재실행·질문이 필요하다는 규칙 결과는 그대로 둠 (다음 행동은 규칙만으로도 정해짐).

    Args:
        rules: 검증 에이전트가 실패 전에 만든 규칙 검사 결과.

    Returns:
        VerificationResult: 통과 상태면 재확인 필요로 바꾼 결과, 아니면 규칙 결과 그대로.
    """
    if rules.status not in (VerificationStatus.APPROVED, VerificationStatus.APPROVED_WITH_WARNINGS):
        return rules
    return rules.model_copy(update={
        "status": VerificationStatus.REVISION_REQUIRED,
        "review_summary": "검증 모델 검토를 마치지 못해 규칙 검사 결과만 반영함",
    })
