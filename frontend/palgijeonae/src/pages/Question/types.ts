import type { Question } from "@/api/product";
import type { ProcessingStatusType, ResultStatus, SourceType } from "@/api/types";

/** 질문 화면에 필요한 상품 정보와 question을 담은 타입 */
export interface QuestionProduct {
    productId: string
    diagnosesId: string
    productName: string
    productImageUrl: string | null
    resultStatus: ResultStatus | null
    processingStatus: ProcessingStatusType
    sourceType: SourceType
    questions: Question[]
}

/** 답변 제출(POST) 시 보낼 형태. */
export interface AnswerSubmission {
    questionId: string
    answerText: string
}
