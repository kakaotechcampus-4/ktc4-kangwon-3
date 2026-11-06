import type { ProductResult, Question } from '@/api/product'
import { ProcessingStatusType, SourceType } from '@/api/types'

// 질문은 최대 2회차까지만 생성된다. (BE 콜백 검증: questionRound는 @Min(1) @Max(2)) questionOrder는 한 회차 안에서의 순서다.
const MAX_QUESTION_ROUND = 2

export const buildQuestion = (overrides: Partial<Question> = {}): Question => {
  const question: Question = {
    questionId: 'question-1',
    questionRound: 1,
    questionOrder: 1,
    questionText: '배터리가 내장되어 있나요?',
    helpText: null,
    answerText: null,
    ...overrides,
  }

  if (question.questionRound < 1 || question.questionRound > MAX_QUESTION_ROUND) {
    throw new Error(`questionRound는 1~${MAX_QUESTION_ROUND}만 가능합니다: ${question.questionRound}`)
  }

  return question
}

// 질문 화면 기본값: 답변을 기다리는(AWAITING_INPUT) 상품과 1회차 질문 하나.
export const buildProductResult = (overrides: Partial<ProductResult> = {}): ProductResult => ({
  productId: 'product-1',
  diagnosesId: 'diagnoses-1',
  productName: '테스트 상품',
  productImageUrl: null,
  sourceType: SourceType.Url,
  sourceUrl: 'https://example.com/item',
  sourceText: null,
  imageUrls: [],
  processingStatus: ProcessingStatusType.AwaitingInput,
  progresses: [],
  questions: [buildQuestion()],
  failure: null,
  assessmentStatus: null,
  resultStatus: null,
  summary: null,
  toolReviews: [],
  requiredActions: [],
  notices: [],
  ...overrides,
})
