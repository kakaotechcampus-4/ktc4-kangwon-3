"""전체 흐름을 연결할 파이프라인 뼈대."""

from ..schemas.agent import ExtractionInput
from ..schemas.schemas import FinalAssessment


class CompliancePipeline:
    """에이전트의 판단을 직접 구현하지 않고 실행 순서와 상태를 관리한다."""

    def run(self, source: ExtractionInput) -> FinalAssessment:
        # TODO: 추출 → 선택·툴 실행 → 결과 종합 → 검증 순서로 연결
        raise NotImplementedError("파이프라인 담당자가 구현할 예정입니다.")
