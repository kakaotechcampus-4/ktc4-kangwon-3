import {
    AssessmentStatus,
    Determination,
    type Finding,
    PipelineStage,
    type ProductResult,
    RiskLevel,
    StageStatus,
    ToolName,
    ToolReviewStatus,
} from "@/api/product";
import { ProcessingStatusType, ResultStatus, SourceType } from "@/api/types";

// 메인 페이지 미리보기에서 쓰는 빈 콜백. 미리보기는 PreviewFrame(inert)로 감싸져 실제로 호출될 일이 없다.
export const NOOP = () => {};

const BASE_PRODUCT: ProductResult = {
    productId: "",
    diagnosesId: "",
    productName: "",
    productImageUrl: null,
    sourceType: SourceType.Url,
    sourceUrl: null,
    sourceText: null,
    imageUrls: [],
    processingStatus: ProcessingStatusType.Pending,
    progresses: [],
    questions: [],
    failure: null,
    assessmentStatus: null,
    resultStatus: null,
    summary: null,
    toolReviews: [],
    requiredActions: [],
    notices: [],
};

/** 미리보기용 ProductResult를 만든다. 지정하지 않은 필드는 빈 값/null로 채워진다. */
export function makePreviewProduct(overrides: Partial<ProductResult>): ProductResult {
    return { ...BASE_PRODUCT, ...overrides };
}

// ── 분야별 예시 Finding (에이전트 소개 섹션용) ──────────────────────────────
// 통관/전기 안전/전파/어린이 제품은 아래 PREVIEW_PRODUCTS의 toolReviews에도 그대로 들어간다.

const RADIO_FINDING: Finding = {
    productFindingId: "preview-finding-radio",
    subject: "전파 적합성평가 (KC 적합인증)",
    determination: Determination.Required,
    riskLevel: RiskLevel.High,
    summary: "사입해서 판매하려면 KC 적합인증을 먼저 받아야 합니다.",
    rationale: "블루투스 5.3(2.4GHz 대역) 송수신 모듈이 있어 방송통신기자재로 분류됩니다.",
    legalSources: [
        {
            findingLegalSourceId: "preview-legal-radio",
            sourceName: "국가법령정보센터",
            lawName: "전파법",
            article: "제58조의2 제1항",
            quotedText: null,
            sourceUrl: null,
            effectiveDate: null,
        },
    ],
};

const ELECTRICAL_FINDING: Finding = {
    productFindingId: "preview-finding-electrical",
    subject: "내장 리튬이온 배터리 안전확인",
    determination: Determination.PossiblyRequired,
    riskLevel: RiskLevel.Medium,
    summary: "기기 내장형 배터리라 별도 안전확인 대상이 아닐 수 있지만 공급사 시험성적서 확인이 필요합니다.",
    rationale: "상세페이지의 배터리 표기만으로는 셀 단품 인증 여부를 알 수 없습니다.",
    legalSources: [
        {
            findingLegalSourceId: "preview-legal-electrical",
            sourceName: "국가법령정보센터",
            lawName: "전기용품 및 생활용품 안전관리법",
            article: "제5조",
            quotedText: null,
            sourceUrl: null,
            effectiveDate: null,
        },
    ],
};

const LABEL_AD_FINDING: Finding = {
    productFindingId: "preview-finding-labelAd",
    subject: "'노이즈 100% 차단' 표현",
    determination: Determination.PossiblyRequired,
    riskLevel: RiskLevel.Medium,
    summary: "절대적 표현이라 근거 자료 없이 쓰면 부당한 표시·광고로 볼 수 있어요.",
    rationale: "상세페이지 문구에 '100% 차단'이라는 절대적 표현이 포함돼 있어요.",
    legalSources: [
        {
            findingLegalSourceId: "preview-legal-labelAd",
            sourceName: "국가법령정보센터",
            lawName: "표시·광고의 공정화에 관한 법률",
            article: "제3조",
            quotedText: null,
            sourceUrl: null,
            effectiveDate: null,
        },
    ],
};

const CUSTOMS_FINDING: Finding = {
    productFindingId: "preview-finding-customs",
    subject: "세관장확인 대상",
    determination: Determination.NotRequired,
    riskLevel: RiskLevel.Low,
    summary: "일반 가구류로 세관장확인 대상이 아닙니다.",
    rationale: "전기·전파·식품·어린이제품 어디에도 해당하지 않습니다.",
    legalSources: [
        {
            findingLegalSourceId: "preview-legal-customs",
            sourceName: "국가법령정보센터",
            lawName: "관세법",
            article: "제226조",
            quotedText: null,
            sourceUrl: null,
            effectiveDate: null,
        },
    ],
};

const CHILDREN_FINDING: Finding = {
    productFindingId: "preview-finding-children",
    subject: "어린이제품 안전기준 대상 여부",
    determination: Determination.InsufficientInformation,
    riskLevel: RiskLevel.Unknown,
    summary: "실내화 소재와 사용 연령 정보가 부족해 판단할 수 없습니다.",
    rationale: "상세페이지에 소재 성분표와 정확한 사용 연령이 표기되어 있지 않습니다.",
    legalSources: [
        {
            findingLegalSourceId: "preview-legal-children",
            sourceName: "국가법령정보센터",
            lawName: "어린이제품 안전 특별법",
            article: null,
            quotedText: null,
            sourceUrl: null,
            effectiveDate: null,
        },
    ],
};

// 식품·의약품 예시는 EARPHONE/TABLE/SLIPPER에 속하지 않는 별도 예시 상품("실리콘 접이식 도시락통 3종")을 쓴다.
const FOOD_DRUG_FINDING: Finding = {
    productFindingId: "preview-finding-foodDrug",
    subject: "식품용 기구 수입신고",
    determination: Determination.PossiblyRequired,
    riskLevel: RiskLevel.Medium,
    summary: "음식에 직접 닿는 용기라 식품용 기구로 수입신고가 필요할 수 있어요.",
    rationale: "실리콘 재질의 도시락통이 음식과 직접 접촉하는 용기로 쓰입니다.",
    legalSources: [
        {
            findingLegalSourceId: "preview-legal-foodDrug",
            sourceName: "국가법령정보센터",
            lawName: "수입식품안전관리 특별법",
            article: "제20조",
            quotedText: null,
            sourceUrl: null,
            effectiveDate: null,
        },
    ],
};

// ── 상품 미리보기 데이터 ────────────────────────────────────────────────

const EARPHONE_NAME = "블루투스 5.3 무선 이어폰 TWS 충전케이스 포함";
const EARPHONE_URL = "https://detail.1688.com/offer/739214086512.html";
const TABLE_NAME = "접이식 캠핑 테이블 알루미늄";
const SLIPPER_NAME = "유아용 실내화 (130~160mm)";
const SLIPPER_CONTENT = "儿童室内拖鞋 유아용 실내화\n사이즈 130 / 140 / 150 / 160mm\n미끄럼 방지 바닥, 통기성 좋은 소재";

/** 진단 진행 중(법령 검토 단계) 상태의 이어폰. Judgement/HowToUse 미리보기에서 쓴다. */
const earphoneInProgress = makePreviewProduct({
    productId: "preview-earphone",
    diagnosesId: "preview-diagnoses",
    productName: EARPHONE_NAME,
    sourceType: SourceType.Url,
    sourceUrl: EARPHONE_URL,
    processingStatus: ProcessingStatusType.InProgress,
    progresses: [
        { stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Completed },
        { stage: PipelineStage.Selection, toolName: null, stageStatus: StageStatus.Completed },
        { stage: PipelineStage.ToolExecution, toolName: ToolName.Radio, stageStatus: StageStatus.Started },
    ],
});

/** 진단 완료(사입 인증 필요) 상태의 이어폰. Result/AgentIntro 미리보기에서 쓴다. */
const earphoneResult = makePreviewProduct({
    productId: "preview-earphone",
    diagnosesId: "preview-diagnoses",
    productName: EARPHONE_NAME,
    sourceType: SourceType.Url,
    sourceUrl: EARPHONE_URL,
    processingStatus: ProcessingStatusType.Completed,
    assessmentStatus: AssessmentStatus.Completed,
    resultStatus: ResultStatus.DirectImportCertificationRequired,
    summary: "블루투스 무선기기로 전파법상 적합성평가 대상이라 사입 전 KC 전파인증이 필요합니다. 구매대행은 개인 사용 목적 면제 범위 안에서 가능합니다.",
    toolReviews: [
        { productToolReviewId: "preview-review-radio", toolName: ToolName.Radio, status: ToolReviewStatus.Completed, message: null, findings: [RADIO_FINDING] },
        { productToolReviewId: "preview-review-electrical", toolName: ToolName.Electrical, status: ToolReviewStatus.Completed, message: null, findings: [ELECTRICAL_FINDING] },
        { productToolReviewId: "preview-review-labelAd", toolName: ToolName.LabelAd, status: ToolReviewStatus.Completed, message: null, findings: [LABEL_AD_FINDING] },
    ],
    requiredActions: [
        "공급사에 블루투스 모듈의 시험성적서와 배터리 IEC 62133 성적서를 요청하세요.",
        "국립전파연구원 전파인증 시스템에서 지정시험기관을 통해 KC 적합인증을 신청하세요.",
        "인증을 받으면 상세페이지와 포장에 KC 인증번호, 수입자명, 제조국을 한글로 표시하세요.",
    ],
});

/** 진단 완료(구매 대행 가능) 상태의 캠핑 테이블. */
const table = makePreviewProduct({
    productId: "preview-table",
    diagnosesId: "preview-diagnoses",
    productName: TABLE_NAME,
    sourceType: SourceType.Url,
    sourceUrl: "https://detail.1688.com/offer/example-camping-table.html",
    processingStatus: ProcessingStatusType.Completed,
    assessmentStatus: AssessmentStatus.Completed,
    resultStatus: ResultStatus.PurchasingAgentAllowed,
    summary: "전기·전파 요소가 없어 구매대행이 가능합니다.",
    toolReviews: [
        { productToolReviewId: "preview-review-customs", toolName: ToolName.Customs, status: ToolReviewStatus.Completed, message: null, findings: [CUSTOMS_FINDING] },
    ],
});

/** 답변 대기(질문 2개, 1개 답변완료) 상태의 유아용 실내화. */
const slipperAwaiting = makePreviewProduct({
    productId: "preview-slipper",
    diagnosesId: "preview-diagnoses",
    productName: SLIPPER_NAME,
    sourceType: SourceType.TextImage,
    sourceText: SLIPPER_CONTENT,
    processingStatus: ProcessingStatusType.AwaitingInput,
    progresses: [
        { stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Completed },
        { stage: PipelineStage.Selection, toolName: null, stageStatus: StageStatus.Completed },
        { stage: PipelineStage.ToolExecution, toolName: ToolName.Electrical, stageStatus: StageStatus.Started },
    ],
    questions: [
        {
            questionId: "preview-question-1",
            questionRound: 1,
            questionOrder: 1,
            questionText: "이 상품을 구매대행으로 파나요, 아니면 미리 사입해서 파나요?",
            helpText: "주문을 받은 뒤 공급사가 소비자에게 바로 보내면 구매대행, 미리 재고를 들여와 창고에 두면 사입입니다.",
            answerText: "사입해서 재고를 들여온 뒤 판매할 예정입니다.",
        },
        {
            questionId: "preview-question-2",
            questionRound: 1,
            questionOrder: 2,
            questionText: "공급사가 KC 관련 서류(시험성적서·확인서 등)를 갖고 있나요?",
            helpText: "서류가 없으면 통관 및 판매가 제한될 수 있습니다.",
            answerText: "",
        },
    ],
});

/** 진단 완료(재확인 필요) 상태의 유아용 실내화. */
const slipperResult = makePreviewProduct({
    productId: "preview-slipper",
    diagnosesId: "preview-diagnoses",
    productName: SLIPPER_NAME,
    sourceType: SourceType.TextImage,
    sourceText: SLIPPER_CONTENT,
    processingStatus: ProcessingStatusType.Completed,
    assessmentStatus: AssessmentStatus.Incomplete,
    resultStatus: ResultStatus.RecheckRequired,
    summary: "상세페이지 정보만으로는 어린이제품 안전기준 대상 여부를 확정하기 어려워 재확인이 필요합니다.",
    toolReviews: [
        { productToolReviewId: "preview-review-children", toolName: ToolName.Children, status: ToolReviewStatus.Incomplete, message: null, findings: [CHILDREN_FINDING] },
    ],
    requiredActions: ["공급사에 소재 성분표와 사용 연령 기준을 확인해달라고 요청하세요."],
});

export const PREVIEW_PRODUCTS = {
    earphoneInProgress,
    earphoneResult,
    table,
    slipperAwaiting,
    slipperResult,
};

// ── 에이전트 소개 섹션 예시 ──────────────────────────────────────────────

interface AgentExample {
    finding: Finding
    exampleProductName: string
}

export const AGENT_EXAMPLE_FINDINGS: Record<ToolName, AgentExample> = {
    [ToolName.Customs]: { finding: CUSTOMS_FINDING, exampleProductName: TABLE_NAME },
    [ToolName.Children]: { finding: CHILDREN_FINDING, exampleProductName: SLIPPER_NAME },
    [ToolName.Electrical]: { finding: ELECTRICAL_FINDING, exampleProductName: EARPHONE_NAME },
    [ToolName.Radio]: { finding: RADIO_FINDING, exampleProductName: EARPHONE_NAME },
    [ToolName.FoodDrug]: { finding: FOOD_DRUG_FINDING, exampleProductName: "실리콘 접이식 도시락통 3종" },
    [ToolName.LabelAd]: { finding: LABEL_AD_FINDING, exampleProductName: EARPHONE_NAME },
};

// ── 마이페이지 안내 섹션 ────────────────────────────────────────────────

// Mypage/index.tsx의 RevisionNoticeBanner 문구/날짜를 그대로 가져온다.
export const REVISION_NOTICE = {
    revisedDate: "2026-09-03",
    title: "어린이제품 안전 특별법 시행규칙 별표2가 개정되었습니다. 완구 세부 기준 중 배터리 관련 표시 항목이 조정되었습니다.",
    description: "사입으로 등록한 상품 1개는 재확인이 필요합니다. 구매대행 상품은 이 조문의 적용을 받지 않아 영향이 없습니다.",
};
