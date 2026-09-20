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
