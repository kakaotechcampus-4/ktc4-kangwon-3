package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

// 결과 카드의 분야별 검토 상태
public enum ToolReviewStatus {
    COMPLETED,
    SKIPPED,

    // 일부 또는 전부를 확인하지 못함(정보 부족). 실패가 아니므로 재호출 대상으로 보지 않는다.
    INCOMPLETE,
}
