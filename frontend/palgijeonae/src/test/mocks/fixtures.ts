import type { LawAmendment, RecheckProduct } from '@/api/lawAmendments'
import { ProcessingStatusType, ResultStatus, SourceType } from '@/api/types/common'
import {
  Determination,
  type DiagnosesDetail,
  type Finding,
  type ProductFailure,
  type ProductResult,
  type Question,
  RiskLevel,
  ToolName,
  type ToolReview,
  ToolReviewStatus,
} from '@/api/types/product'
import { SocialProvider, type UserInfo } from '@/api/users'
import type { MyProductItem } from '@/pages/Products/types'

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

// 진단 실패 정보. 기본값은 다시 시도하면 성공할 수 있는(retryable) 실패다.
export const buildFailure = (overrides: Partial<ProductFailure> = {}): ProductFailure => ({
  failedStage: null,
  errorCode: 'PIPELINE-001',
  errorMessage: '진단 중 일시적인 오류가 발생했어요.',
  retryable: true,
  ...overrides,
})

// 진단서 조회(진단 진행 화면) 응답. 기본값은 진행 중인 상품 하나이고, pollIntervalMs가 null이라 폴링하지 않는다.
export const buildDiagnosesDetail = (overrides: Partial<DiagnosesDetail> = {}): DiagnosesDetail => ({
  diagnosesId: 'diagnoses-1',
  processingStatus: ProcessingStatusType.InProgress,
  pollIntervalMs: null,
  products: [buildProductResult({ processingStatus: ProcessingStatusType.InProgress, questions: [] })],
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
  ...overrides,
})

// 마이페이지 목록의 상품 하나. 기본값은 진단이 끝난 사입 가능 상품이다.
export const buildMyProduct = (overrides: Partial<MyProductItem> = {}): MyProductItem => ({
  productId: 'product-1',
  diagnosesId: 'diagnoses-1',
  productName: '테스트 상품',
  productImageUrl: null,
  sourceType: SourceType.Url,
  processingStatus: ProcessingStatusType.Completed,
  resultStatus: ResultStatus.PurchasingAgentAllowed,
  createdAt: '2026-01-01T00:00:00Z',
  ...overrides,
})

export const buildUserInfo = (overrides: Partial<UserInfo> = {}): UserInfo => ({
  name: '홍길동',
  email: 'gildong@example.com',
  socialProvider: SocialProvider.Kakao,
  ...overrides,
})

// 개정 알림에 담긴 재진단 대상 상품 하나
export const buildRecheckProduct = (overrides: Partial<RecheckProduct> = {}): RecheckProduct => ({
  productId: 'product-1',
  diagnosesId: 'diagnoses-1',
  productName: '테스트 상품',
  ...overrides,
})

// 법령 개정 알림 하나. 기본값은 상품 하나가 걸린 일부개정이다.
export const buildLawAmendment = (overrides: Partial<LawAmendment> = {}): LawAmendment => ({
  lawAmendmentId: 'law-amendment-1',
  lawName: '전기용품 및 생활용품 안전관리법 시행규칙',
  revisionType: '일부개정',
  toolName: ToolName.Electrical,
  enforceDate: '2026-12-01',
  products: [buildRecheckProduct()],
  ...overrides,
})

// 분야 카드 안의 판정 항목 하나. 기본값은 조치가 필요한 항목이다.
export const buildFinding = (overrides: Partial<Finding> = {}): Finding => ({
  productFindingId: 'finding-1',
  subject: '전기용품 안전인증',
  determination: Determination.Required,
  riskLevel: RiskLevel.High,
  summary: '안전인증이 필요한 상품이에요.',
  rationale: '전기용품 및 생활용품 안전관리법에 따라 인증이 필요해요.',
  legalSources: [],
  ...overrides,
})

// 분야별 검토 카드 하나. 기본값은 판정 항목이 하나 있는 검토 완료 분야다.
export const buildToolReview = (overrides: Partial<ToolReview> = {}): ToolReview => ({
  productToolReviewId: 'tool-review-1',
  toolName: ToolName.Electrical,
  status: ToolReviewStatus.Completed,
  message: null,
  findings: [buildFinding()],
  ...overrides,
})
