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
    resultStatus: ResultStatus
    createdAt: Date
}

export type ProductFilter = "all" | ResultStatus;

export interface PageInfo {
    page: number
    size: number
    totalElements: number
    totalPages: number
    hasNext: boolean
}
