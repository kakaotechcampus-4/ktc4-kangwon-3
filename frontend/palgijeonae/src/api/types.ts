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
 * - RecheckRequired: 재검토 필요 (개정됨)
*/
export enum ResultStatus {
    PurchasingAgentAllowed = "PURCHASING_AGENT_ALLOWED",
    DirectImportCertificationRequired = "DIRECT_IMPORT_CERTIFICATION_REQUIRED",
    RecheckRequired = "RECHECK_REQUIRED",
}