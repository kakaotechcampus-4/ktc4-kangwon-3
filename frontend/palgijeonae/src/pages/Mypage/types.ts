import { type ProcessingStatusType, type ResultStatus, SourceType } from "@/api/types.ts"

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
