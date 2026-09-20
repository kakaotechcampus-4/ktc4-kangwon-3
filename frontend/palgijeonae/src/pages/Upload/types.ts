export interface Product {
    id: string
    type: "url" | "text/image"
    title: string
    thumbnail?: string
    // 대표 이미지 원본 File. thumbnail은 미리보기용 blob URL이라 presigned 업로드에 쓸 수 없어 별도로 들고 있는다.
    productImageFile?: File
    link?: string
    content?: string
    images?: File[]
}

// 상품별 진단 요청 진행 상태. Product 자체는 입력 폼이 다루는 도메인 데이터라 섞지 않고 따로 관리한다.
export type DiagnosisStatus =
    | { state: "pending" }
    | { state: "success"; diagnosesId: number }
    | { state: "failed" }
