"""검증 담당자가 구현할 에이전트 뼈대."""

from ..schemas.schemas import DraftAssessment, VerificationResult


class VerificationAgent:
    """종합된 심사 결과의 근거·누락·모순을 검증한다."""

    def verify(self, draft: DraftAssessment) -> VerificationResult:
        """
        입력: 결과 종합 툴이 만든 DraftAssessment
        출력: 검증 상태·지적 사항·추가 조치 요청을 담은 VerificationResult
        """
        # TODO: LangChain 모델과 verification 프롬프트 연결
        # TODO: 상품 정보 대비 심사 누락·조회 실패·근거 없는 판단 확인
        # TODO: VerificationResult 반환 (재실행 제어는 파이프라인 담당)
        raise NotImplementedError("검증 담당자가 구현할 예정입니다.")
