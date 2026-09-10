package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

public enum ResultStatus {
    // 구매 대행 가능
    PURCHASING_AGENT_ALLOWED,

    // 사입 인증 필요
    DIRECT_IMPORT_CERTIFICATION_REQUIRED,

    // 재확인 필요
    RECHECK_REQUIRED,
}
