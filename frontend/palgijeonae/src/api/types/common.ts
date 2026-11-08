/** 상품 등록 방식. URL 입력 / 텍스트·이미지 입력 */
export enum SourceType {
    Url = "URL",
    TextImage = "TEXT_IMAGE",
}

/** 진단 처리 상태
 * - Pending: 진단 대기 중
 * - InProgress: 진단 진행 중
 * - AwaitingInput: 진단 진행 중, 추가 입력(질문) 필요
 * - Completed: 진단 완료
 * - Failed: 진단 실패
*/
export enum ProcessingStatusType {
    Pending = "PENDING",
    InProgress = "IN_PROGRESS",
    AwaitingInput = "AWAITING_INPUT",
    Completed = "COMPLETED",
    Failed = "FAILED",
}

/** 진단이 완료된 상품의 결과 상태
 * - PurchasingAgentAllowed: 구매대행 허용
 * - DirectImportCertificationRequired: 직수입 인증 필요
 * - RecheckRequired: AI가 판정을 끝내지 못해 다시 확인이 필요함 (법령 개정과는 별개)
*/
export enum ResultStatus {
    PurchasingAgentAllowed = "PURCHASING_AGENT_ALLOWED",
    DirectImportCertificationRequired = "DIRECT_IMPORT_CERTIFICATION_REQUIRED",
    RecheckRequired = "RECHECK_REQUIRED",
}