/** 하나의 질문 요소 */
export interface QuestionItem {
    id: string
    title: string
    description?: string
}

/** 상품 하나에 대한 질문 목록 */
export interface ProductQuestions {
    productId: string
    productName: string
    questions: QuestionItem[]
}

/** 답변 제출(POST) 시 보낼 형태. */
export interface AnswerSubmission {
    questionId: string
    answer: string
}

/** 제품별 답변 완료 상태 */
export type ProductStatus = "complete" | "partial" | "empty";
