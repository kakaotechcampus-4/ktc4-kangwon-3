"""파이프라인 단계 자리에 넣는 진단 단계 어댑터. 단계 고유 업무 로직만 둠 (진행 알림·trace 등은 hook)."""

from ..pipeline.extraction_step import ExtractionStep
from ..schemas.agent import ExtractionInput
from ..schemas.product import Product
from ..schemas.session import DiagnosisInput
from .answers import with_answers


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
