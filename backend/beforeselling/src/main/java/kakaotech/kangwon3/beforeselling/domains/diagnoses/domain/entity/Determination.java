package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

// 판단 항목 하나의 요건 해당 여부
public enum Determination {
    REQUIRED,
    NOT_REQUIRED,
    POSSIBLY_REQUIRED,
    INSUFFICIENT_INFORMATION,
    NOT_APPLICABLE,
}
