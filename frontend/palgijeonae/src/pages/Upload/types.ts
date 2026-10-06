export interface Product {
    id: string
    type: "url" | "text/image"
    title: string
    // 대표 이미지 원본 File. 미리보기 blob URL은 AddedProduct가 이 File로부터 직접 만들고 관리한다.
    productImageFile?: File
    link?: string
    content?: string
    // 상세페이지 이미지 원본 File들. 위와 같은 이유로 들고 있는다.
    images?: File[]
}

export type SourceType = "URL" | "TEXT_IMAGE";

// 진단 요청을 위한 product item.
export interface DiagnosisProductPayload {
    productName: string
    productImageKey?: string
    sourceType: SourceType
    sourceUrl?: string
    sourceText?: string
    imageKeys?: string[]
}
