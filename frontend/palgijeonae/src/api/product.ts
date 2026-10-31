import type { ProcessingStatusType, ResultStatus, SourceType } from "@/api/types";

/** 진단 결과를 검토한 규제 분야
 * - Customs: 통관
 * - Children: 어린이제품
 * - Electrical: 전기안전
 * - Radio: 전파
 * - FoodDrug: 식약
 * - LabelAd: 표시광고
*/
export enum ToolName {
    Customs = "CUSTOMS",
    Children = "CHILDREN",
    Electrical = "ELECTRICAL",
    Radio = "RADIO",
    FoodDrug = "FOOD_DRUG",
    LabelAd = "LABEL_AD",
}

/** 진단 결과 전체 완료 여부. 입력 대기 등으로 아직 안 끝났으면 Incomplete
 * - Completed: 완료
 * - Incomplete: 미완료
*/
export enum AssessmentStatus {
    Completed = "COMPLETED",
    Incomplete = "INCOMPLETE",
}

/** 분야별 검토 카드의 진행 상태
 * - Completed: 해당 분야 검토를 마침
 * - Skipped: 검토하지 않은 분야
 * - Incomplete: 일부 또는 전부를 확인하지 못함
*/
export enum ToolReviewStatus {
    Completed = "COMPLETED",
    Skipped = "SKIPPED",
    Incomplete = "INCOMPLETE",
}

/** 개별 판정 항목의 필요 여부 판단. 실행 오류와 정보 부족을 구분해서 사용
 * - Required: 필요
 * - NotRequired: 불필요
 * - PossiblyRequired: 필요할 수 있음 (확정 아님)
 * - InsufficientInformation: 정보 부족으로 판단 불가
 * - NotApplicable: 해당 없음 (규제 비대상)
*/
export enum Determination {
    Required = "REQUIRED",
    NotRequired = "NOT_REQUIRED",
    PossiblyRequired = "POSSIBLY_REQUIRED",
    InsufficientInformation = "INSUFFICIENT_INFORMATION",
    NotApplicable = "NOT_APPLICABLE",
}

/** 개별 판정 항목의 위험도. Unknown은 낮은 위험이 아니라 판단하지 못한 상태
 * - Low: 낮음
 * - Medium: 중간
 * - High: 높음
 * - Unknown: 판단 불가
*/
export enum RiskLevel {
    Low = "LOW",
    Medium = "MEDIUM",
    High = "HIGH",
    Unknown = "UNKNOWN",
}

/** 진단 파이프라인 단계 */
export enum PipelineStage {
    Extraction = "EXTRACTION",
    Selection = "SELECTION",
    ToolExecution = "TOOL_EXECUTION",
    Aggregation = "AGGREGATION",
    Verification = "VERIFICATION",
    Finalization = "FINALIZATION",
}

/** 진행 단계 하나의 상태
 * - Started: 시작됨
 * - Completed: 완료됨
 * - Skipped: 건너뜀
*/
export enum StageStatus {
    Started = "STARTED",
    Completed = "COMPLETED",
    Skipped = "SKIPPED",
}

/**
 * 판정 근거가 된 법령 출처
 * - sourceName: 출처 이름 (예: 국가법령정보센터)
 * - lawName / article: 근거가 된 법령명과 조문
 * - quotedText: 근거 법령 원문 인용
 * - sourceUrl: 출처로 이동할 수 있는 링크
 * - effectiveDate: 해당 법령의 시행일
 */
export interface LegalSource {
    findingLegalSourceId: string
    sourceName: string
    lawName: string | null
    article: string | null
    quotedText: string | null
    sourceUrl: string | null
    effectiveDate: string | null
}

/**
 * 분야 카드 안의 개별 판정 항목
 * - subject: 무엇에 대한 판정인지 (예: "전파 적합성평가")
 * - summary: 판정 결과 한 줄 요약
 * - rationale: 왜 그렇게 판정했는지에 대한 설명
 */
export interface Finding {
    productFindingId: string
    subject: string
    determination: Determination
    riskLevel: RiskLevel
    summary: string
    rationale: string
    legalSources: LegalSource[]
}

/**
 * 규제 분야 하나에 대한 검토 카드
 * - message: 이 분야 전체에 대한 안내 문구
 * - findings: 이 분야에서 찾아낸 개별 판정 항목들
 */
export interface ToolReview {
    productToolReviewId: string
    toolName: ToolName
    status: ToolReviewStatus
    message: string | null
    findings: Finding[]
}

/** 진단 진행 화면에서 보여줄, 단계·Tool별 최신 상태 하나 */
export interface ProductProgress {
    stage: PipelineStage
    // stage가 ToolExecution일 때만 값이 있고, 단계 자체의 진행이면 null
    toolName: ToolName | null
    stageStatus: StageStatus
}

/** 진단 중 사용자에게 묻는 질문 하나
 * - questionRound: 질문 회차 (답변 후 재진단에서 다시 물으면 2)
 * - helpText: 질문 보조 설명. 없으면 null
 * - answerText: 답변하기 전에는 null
 */
export interface Question {
    questionId: string
    questionRound: number
    questionOrder: number
    questionText: string
    helpText: string | null
    answerText: string | null
}

/** 진단 실패 정보. processingStatus가 Failed일 때만 값이 있음
 * - failedStage: 실패한 단계. 진단 시작 전 실패나 결과를 받지 못해 종료한 경우 null
 * - retryable: 다시 진단하면 성공할 수 있는지. 알 수 없으면 null
 */
export interface ProductFailure {
    failedStage: PipelineStage | null
    errorCode: string
    errorMessage: string
    retryable: boolean | null
}

/**
 * 상품 단건(GET /api/v1/products/{productId})/진단서(GET /api/v1/diagnoses/{diagnosesId}) 조회 응답이
 * 공유하는 상품 하나의 형태. Result 페이지와 진단 진행(폴링) 화면이 함께 쓴다.
 * 결과 전에는 관련 필드가 null/빈 배열.
 */
export interface ProductResult {
    productId: string
    diagnosesId: string
    productName: string
    productImageUrl: string | null
    sourceType: SourceType
    sourceUrl: string | null
    sourceText: string | null
    imageUrls: string[]
    processingStatus: ProcessingStatusType
    progresses: ProductProgress[]
    questions: Question[]
    failure: ProductFailure | null
    assessmentStatus: AssessmentStatus | null
    resultStatus: ResultStatus | null
    summary: string | null
    toolReviews: ToolReview[]
    requiredActions: string[]
    notices: string[]
}

/** GET /api/v1/diagnoses/{diagnosesId} 응답 전체. */
export interface DiagnosesDetail {
    diagnosesId: string
    processingStatus: ProcessingStatusType
    // 대기·진행 중인 상품이 하나라도 있으면 값이 있고, 없으면 null(폴링 중단).
    pollIntervalMs: number | null
    products: ProductResult[]
    createdAt: string
    updatedAt: string
}
