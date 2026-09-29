export interface QuestionItem {
    id: string
    title: string
    description?: string
}

// 상품 하나에 대한 질문 목록. GET 응답 모양을 그대로 옮긴다.
export interface ProductQuestions {
    productId: string
    productName: string
    questions: QuestionItem[]
}

// 답변 제출(POST) 시 보낼 형태.
export interface AnswerSubmission {
    questionId: string
    answer: string
}
