export interface Product {
    id: string
    type: "url" | "text/image"
    title: string
    thumbnail?: string
    link?: string
    content?: string
    images?: File[]
}
