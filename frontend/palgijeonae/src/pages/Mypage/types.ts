// 진단서 목록 조회에 쓰이는 타입들
export type SourceType = 
    | "URL"
    | "TEXT_IMAGE"

export type ProcessingStatusType = 
    | "PENDING" 
    | "IN_PROGRESS" 
    | "AWAITING_INPUT" 
    | "COMPLETED" 
    | "FAILED";

export type ResultStatus =
    | "PURCHASING_AGENT_ALLOWED"
    | "DIRECT_IMPORT_CERTIFICATION_REQUIRED"
    | "RECHECK_REQUIRED";


export interface MyProductItem {
    productId: string
    productName: string
    productImageUrl?: string
    sourceType: SourceType
    processingStatus: ProcessingStatusType
    resultStatus?: ResultStatus
    createdAt: Date
}

// 검색 필터 탭에 쓰이는 타입
export type ProductFilter = "all" | ResultStatus;

// 진단서 목록 조회 시 페이지 정보를 나타내는 타입
export interface PageInfo {
    page: number
    size: number
    totalElements: number
    totalPages: number
    hasNext: boolean
}
