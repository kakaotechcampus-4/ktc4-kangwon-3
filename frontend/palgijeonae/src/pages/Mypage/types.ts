/** 상품 등록 방식. URL 입력 / 텍스트·이미지 입력 */
export type SourceType =
    | "URL"
    | "TEXT_IMAGE"

/**
 * 진단 처리 상태.
 * - PENDING: 대기 중
 * - IN_PROGRESS: 진단 중
 * - AWAITING_INPUT: 입력 대기 중
 * - COMPLETED: 진단 완료(결과는 resultStatus에 따로 담김)
 * - FAILED: 진단 실패
 */
export type ProcessingStatusType =
    | "PENDING"
    | "IN_PROGRESS"
    | "AWAITING_INPUT"
    | "COMPLETED"
    | "FAILED";

/**
 * 진단이 완료된 상품의 결과 상태.
 * - PURCHASING_AGENT_ALLOWED: 구매 대행 가능
 * - DIRECT_IMPORT_CERTIFICATION_REQUIRED: 사입 인증 필요
 * - RECHECK_REQUIRED: 재확인 필요
 */
export type ResultStatus =
    | "PURCHASING_AGENT_ALLOWED"
    | "DIRECT_IMPORT_CERTIFICATION_REQUIRED"
    | "RECHECK_REQUIRED";

/**
 * 목록 조회에서 상품 하나의 정보를 담은 타입.
 * - productImageUrl: 대표 이미지가 없으면 null
 * - resultStatus: 진단이 끝나지 않았으면 null
 */
export interface MyProductItem {
    productId: string
    diagnosesId: string
    productName: string
    productImageUrl: string | null
    sourceType: SourceType
    processingStatus: ProcessingStatusType
    resultStatus: ResultStatus | null
    createdAt: string
}

/** 검색 필터 탭에 쓰이는 타입. "all"이면 전체 조회 */
export type ProductFilter = "all" | ResultStatus;

/** 진단서 목록 조회 시 페이지 정보를 나타내는 타입 */
export interface PageInfo {
    page: number
    size: number
    totalElements: number
    totalPages: number
    hasNext: boolean
}
