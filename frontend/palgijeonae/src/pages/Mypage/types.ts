// 백엔드 GET /api/v1/diagnoses 응답의 resultStatus와 동일한 값.
export type ResultStatus =
    | "PURCHASING_AGENT_ALLOWED"
    | "DIRECT_IMPORT_CERTIFICATION_REQUIRED"
    | "RECHECK_REQUIRED";

// TODO: 목록 조회 응답엔 아직 sourceType이 없어서, 실제로는 상세 조회나 API 확장이 필요할 수 있다.
// 지금은 화면 확인용으로 프론트에서 직접 값을 채워 쓴다.
export type ProductInputType = "url" | "text" | "image";

export interface MyProductItem {
    id: number
    title: string
    thumbnail?: string
    inputType: ProductInputType
    resultStatus: ResultStatus
    link?: string
    content?: string
    images?: string[]
}

export type ProductFilter = "all" | ResultStatus;
