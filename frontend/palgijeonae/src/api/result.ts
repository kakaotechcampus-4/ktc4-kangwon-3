// TODO: AI 파이프라인이 연결되면 아래 import문의 주석을 풀기
// import apiClient from "@/api/client";
import {
    AssessmentStatus,
    Determination,
    PipelineStage,
    type ProductResult,
    RiskLevel,
    StageStatus,
    ToolName,
    ToolReviewStatus,
} from "@/api/product";
import { ProcessingStatusType, ResultStatus, SourceType } from "@/api/types";

// TEMP: UI 구현을 위한 목업 데이터. 완료 3건 + 미완료(대기/진행중) 2건.
// TODO: AI 파이프라인이 연결되면 일괄 제거한다.
const MOCK_PRODUCT_RESULTS: ProductResult[] = [
    {
        productId: "mock-product-1",
        productName: "블루투스 5.3 무선 이어폰 TWS 충전케이스 포함",
        productImageUrl: null,
        sourceType: SourceType.Url,
        sourceUrl: "https://detail.1688.com/offer/739281550417.html",
        sourceText: null,
        imageUrls: [],
        processingStatus: ProcessingStatusType.Completed,
        progresses: [],
        questions: [
            {
                questionId: "mock-question-1-1",
                questionRound: 1,
                questionOrder: 1,
                questionText: "이 상품을 구매대행으로 파나요, 아니면 미리 사입해서 파나요?",
                helpText: "주문을 받은 뒤 공급사가 소비자에게 바로 보내면 구매대행, 미리 재고를 들여와 창고에 두면 사입입니다.",
                answerText: "사입해서 재고를 들여온 뒤 판매할 예정입니다.",
            },
            {
                questionId: "mock-question-1-2",
                questionRound: 1,
                questionOrder: 2,
                questionText: "공급사가 KC 관련 서류(시험성적서·확인서 등)를 갖고 있나요?",
                helpText: "서류가 없으면 통관 및 판매가 제한될 수 있습니다.",
                answerText: "잘 모르겠어요. 아직 물어보지 않았습니다.",
            },
            {
                questionId: "mock-question-1-3",
                questionRound: 2,
                questionOrder: 1,
                questionText: "배터리(400mAh 리튬이온)가 셀 단품으로도 별도 인증을 받은 적이 있나요?",
                helpText: null,
                answerText: "확인해봤는데 셀 단품 인증 이력은 없습니다.",
            },
        ],
        failure: null,
        assessmentStatus: AssessmentStatus.Completed,
        resultStatus: ResultStatus.DirectImportCertificationRequired,
        summary: "블루투스 무선기기로 전파법상 적합성평가 대상이라 사입 전 KC 전파인증이 필요합니다. 구매대행은 개인 사용 목적 면제 범위 안에서 가능합니다.",
        toolReviews: [
            {
                productToolReviewId: "mock-review-1-radio",
                toolName: ToolName.Radio,
                status: ToolReviewStatus.Completed,
                message: "2.4GHz 블루투스 송수신 기능이 있어 방송통신기자재 적합성평가 대상 여부를 확인했습니다.",
                findings: [
                    {
                        productFindingId: "mock-finding-1-radio-1",
                        subject: "전파 적합성평가 (KC 적합인증)",
                        determination: Determination.Required,
                        riskLevel: RiskLevel.High,
                        summary: "사입해서 판매하려면 KC 적합인증을 먼저 받아야 합니다.",
                        rationale: "블루투스 5.3(2.4GHz 대역) 송수신 모듈이 있어 방송통신기자재로 분류됩니다.",
                        legalSources: [
                            {
                                findingLegalSourceId: "mock-legal-1-radio-1",
                                sourceName: "국가법령정보센터",
                                lawName: "전파법",
                                article: "제58조의2 제1항",
                                quotedText: "방송통신기자재등을 제조 또는 판매하거나 수입하려는 자는 해당 기자재에 대하여 적합성평가를 받아야 한다.",
                                sourceUrl: null,
                                effectiveDate: "2025-01-21",
                            },
                        ],
                    },
                    {
                        productFindingId: "mock-finding-1-radio-2",
                        subject: "구매대행 개인 사용 면제",
                        determination: Determination.PossiblyRequired,
                        riskLevel: RiskLevel.Medium,
                        summary: "구매대행은 소비자 명의 수입이면 적합성평가 면제를 받을 수 있습니다.",
                        rationale: "답변하신 판매형태는 사입이지만, 같은 상품을 구매대행으로 올리는 경우 1인 1대 개인 사용 목적일 때만 면제됩니다.",
                        legalSources: [
                            {
                                findingLegalSourceId: "mock-legal-1-radio-2",
                                sourceName: "국립전파연구원",
                                lawName: "방송통신기자재등의 적합성평가에 관한 고시",
                                article: null,
                                quotedText: null,
                                sourceUrl: null,
                                effectiveDate: null,
                            },
                        ],
                    },
                ],
            },
            {
                productToolReviewId: "mock-review-1-electrical",
                toolName: ToolName.Electrical,
                status: ToolReviewStatus.Completed,
                message: "충전 케이스에 리튬이온 배터리(400mAh)가 내장되어 전기용품 안전관리 대상인지 확인했습니다.",
                findings: [
                    {
                        productFindingId: "mock-finding-1-electrical-1",
                        subject: "내장 리튬이온 배터리 안전확인",
                        determination: Determination.PossiblyRequired,
                        riskLevel: RiskLevel.Medium,
                        summary: "기기 내장형 배터리라 별도 안전확인 대상이 아닐 수 있지만 공급사 시험성적서 확인이 필요합니다.",
                        rationale: "상세페이지의 배터리 표기가 400mAh 리튬전지뿐이라 셀 단품 인증 여부를 알 수 없습니다.",
                        legalSources: [
                            {
                                findingLegalSourceId: "mock-legal-1-electrical-1",
                                sourceName: "국가법령정보센터",
                                lawName: "전기용품 및 생활용품 안전관리법",
                                article: "제5조",
                                quotedText: null,
                                sourceUrl: null,
                                effectiveDate: null,
                            },
                        ],
                    },
                ],
            },
            {
                productToolReviewId: "mock-review-1-customs",
                toolName: ToolName.Customs,
                status: ToolReviewStatus.Completed,
                message: "HS코드 후보 2개를 기준으로 세관장확인 대상 여부를 확인했습니다.",
                findings: [
                    {
                        productFindingId: "mock-finding-1-customs-1",
                        subject: "세관장확인 대상",
                        determination: Determination.NotRequired,
                        riskLevel: RiskLevel.Low,
                        summary: "HS코드 후보 2개 모두 세관장확인 요건이 없습니다.",
                        rationale: "세관장확인은 수입신고 때 서류만 확인하는 통관 절차로, 국내 판매용 KC 인증 의무와는 별개입니다.",
                        legalSources: [
                            {
                                findingLegalSourceId: "mock-legal-1-customs-1",
                                sourceName: "국가법령정보센터",
                                lawName: "관세법",
                                article: "제226조",
                                quotedText: null,
                                sourceUrl: null,
                                effectiveDate: null,
                            },
                        ],
                    },
                ],
            },
            {
                productToolReviewId: "mock-review-1-labelAd",
                toolName: ToolName.LabelAd,
                status: ToolReviewStatus.Incomplete,
                message: "상세페이지가 중국어 이미지 위주라 표시 항목 일부를 읽지 못했습니다.",
                findings: [
                    {
                        productFindingId: "mock-finding-1-labelAd-1",
                        subject: "수입자·제조국 한글 표시",
                        determination: Determination.InsufficientInformation,
                        riskLevel: RiskLevel.Unknown,
                        summary: "상세페이지에서 수입자·제조국 표시를 찾지 못했습니다.",
                        rationale: "국내에서 판매하려면 제품이나 포장에 수입자명, 제조국, KC 인증번호를 한글로 표시해야 합니다.",
                        legalSources: [],
                    },
                ],
            },
            {
                productToolReviewId: "mock-review-1-children",
                toolName: ToolName.Children,
                status: ToolReviewStatus.Skipped,
                message: "14세 이상 사용 제품으로 확인되어 검토하지 않았습니다.",
                findings: [],
            },
            {
                productToolReviewId: "mock-review-1-foodDrug",
                toolName: ToolName.FoodDrug,
                status: ToolReviewStatus.Skipped,
                message: "성분·식품접촉 항목이 없어 검토하지 않았습니다.",
                findings: [],
            },
        ],
        requiredActions: [
            "공급사에 블루투스 모듈의 시험성적서와 배터리 IEC 62133 성적서를 요청하세요.",
            "국립전파연구원 전파인증 시스템에서 지정시험기관을 통해 KC 적합인증을 신청하세요.",
            "인증을 받으면 상세페이지와 포장에 KC 인증번호, 수입자명, 제조국을 한글로 표시하세요.",
        ],
        notices: [
            "구매대행으로 판매해도 개인 사용 목적 면제 요건(1인 1대)을 벗어나면 인증이 필요합니다.",
        ],
    },
    {
        productId: "mock-product-2",
        productName: "접이식 캠핑 테이블 알루미늄",
        productImageUrl: null,
        sourceType: SourceType.TextImage,
        sourceUrl: null,
        sourceText: `[상품명] 户外折叠铝合金野营桌 便携式野餐桌 超轻野营装备
[材质] 航空级铝合金 + 防水牛津布收纳袋
[规格] 展开尺寸 60*40*40cm / 折叠后 60*8*8cm / 净重 1.8kg
[颜色] 军绿色 / 黑色 / 橙色 (拍下备注颜色,默认发军绿色)
[承重] 最大承重 30kg,日常野餐、烧烤、钓鱼完全够用

【产品特点】
1. 一秒收放,无需安装,打开即用
2. 铝合金材质,防锈防腐蚀,长期户外使用也不变形
3. 自带收纳包,背带可调节,方便携带
4. 桌面做了防滑处理,放置杯具餐具不易打滑

【包装清单】
折叠桌 x1
收纳袋 x1
说明书 x1

【发货说明】
- 本店所有商品均为现货,付款后 48 小时内发货
- 默认韵达/中通快递,偏远地区可能需要补运费,拍前请联系客服确认
- 如遇节假日或大促期间,发货时间可能顺延 2-3 天,敬请谅解

【售后说明】
收到商品如有质量问题,请在 7 天内联系客服,我们会第一时间为您处理。
人为损坏、正常使用磨损不在三包范围内,请知悉。

注:图片均为实拍,因拍摄光线、显示器色差等原因,实物颜色可能与图片略有差异,请以实物为准。`,
        imageUrls: [],
        processingStatus: ProcessingStatusType.Completed,
        progresses: [],
        questions: [],
        failure: null,
        assessmentStatus: AssessmentStatus.Completed,
        resultStatus: ResultStatus.PurchasingAgentAllowed,
        summary: "전기·전파 요소가 없고 별도 인증 대상이 아니라 구매대행이 가능합니다.",
        toolReviews: [
            {
                productToolReviewId: "mock-review-2-customs",
                toolName: ToolName.Customs,
                status: ToolReviewStatus.Completed,
                message: null,
                findings: [
                    {
                        productFindingId: "mock-finding-2-customs-1",
                        subject: "세관장확인 대상",
                        determination: Determination.NotApplicable,
                        riskLevel: RiskLevel.Low,
                        summary: "일반 가구류로 세관장확인 대상이 아닙니다.",
                        rationale: "전기·전파·식품·어린이제품 어디에도 해당하지 않습니다.",
                        legalSources: [],
                    },
                ],
            },
        ],
        requiredActions: [],
        notices: [],
    },
    {
        productId: "mock-product-3",
        productName: "유아용 실내화 (130~160mm)",
        productImageUrl: null,
        sourceType: SourceType.Url,
        sourceUrl: "https://detail.1688.com/offer/example-shoes.html",
        sourceText: null,
        imageUrls: [],
        processingStatus: ProcessingStatusType.Completed,
        progresses: [],
        questions: [],
        failure: null,
        assessmentStatus: AssessmentStatus.Incomplete,
        resultStatus: ResultStatus.RecheckRequired,
        summary: "상세페이지 정보만으로는 어린이제품 안전기준 대상 여부를 확정하기 어려워 재확인이 필요합니다.",
        toolReviews: [
            {
                productToolReviewId: "mock-review-3-children",
                toolName: ToolName.Children,
                status: ToolReviewStatus.Incomplete,
                message: "소재·연령 표시가 부족해 전부 확인하지 못했습니다.",
                findings: [
                    {
                        productFindingId: "mock-finding-3-children-1",
                        subject: "어린이제품 안전기준 대상 여부",
                        determination: Determination.InsufficientInformation,
                        riskLevel: RiskLevel.Unknown,
                        summary: "실내화 소재와 사용 연령 정보가 부족해 판단할 수 없습니다.",
                        rationale: "상세페이지에 소재 성분표와 정확한 사용 연령이 표기되어 있지 않습니다.",
                        legalSources: [],
                    },
                ],
            },
        ],
        requiredActions: ["공급사에 소재 성분표와 사용 연령 기준을 확인해달라고 요청하세요."],
        notices: ["이 진단서는 진단일 기준으로 공개된 법령 정보를 바탕으로 작성되었습니다."],
    },
    {
        productId: "mock-product-4",
        productName: "야광 비즈 팔찌 만들기 DIY 키트 5색",
        productImageUrl: null,
        sourceType: SourceType.TextImage,
        sourceUrl: null,
        sourceText: "夜光串珠手链DIY材料包 5色可选 儿童手工制作套装",
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
    },
    {
        productId: "mock-product-5",
        productName: "스테인리스 보온 텀블러 500ml",
        productImageUrl: null,
        sourceType: SourceType.Url,
        sourceUrl: "https://detail.1688.com/offer/example-tumbler.html",
        sourceText: null,
        imageUrls: [],
        processingStatus: ProcessingStatusType.InProgress,
        progresses: [
            { stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.Selection, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.ToolExecution, toolName: ToolName.Customs, stageStatus: StageStatus.Started },
        ],
        questions: [],
        failure: null,
        assessmentStatus: null,
        resultStatus: null,
        summary: null,
        toolReviews: [],
        requiredActions: [],
        notices: [],
    },
    {
        productId: "mock-product-6",
        productName: "LED 네일아트 건조기 UV 램프",
        productImageUrl: null,
        sourceType: SourceType.Url,
        sourceUrl: "https://detail.1688.com/offer/example-nail-lamp.html",
        sourceText: null,
        imageUrls: [],
        processingStatus: ProcessingStatusType.AwaitingInput,
        progresses: [
            { stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.Selection, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.ToolExecution, toolName: ToolName.Electrical, stageStatus: StageStatus.Started },
        ],
        questions: [
            {
                questionId: "mock-question-6-1",
                questionRound: 1,
                questionOrder: 1,
                questionText: "이 상품을 구매대행으로 파나요, 아니면 미리 사입해서 파나요?",
                helpText: "주문을 받은 뒤 공급사가 소비자에게 바로 보내면 구매대행, 미리 재고를 들여와 창고에 두면 사입입니다.",
                answerText: null,
            },
        ],
        failure: null,
        assessmentStatus: null,
        resultStatus: null,
        summary: null,
        toolReviews: [],
        requiredActions: [],
        notices: [],
    },
    {
        productId: "mock-product-7",
        productName: "무선 미니 가습기 USB 충전식",
        productImageUrl: null,
        sourceType: SourceType.TextImage,
        sourceUrl: null,
        sourceText: "USB로 충전하는 무선 미니 가습기",
        imageUrls: [],
        processingStatus: ProcessingStatusType.Failed,
        progresses: [],
        questions: [],
        failure: null,
        assessmentStatus: null,
        resultStatus: null,
        summary: null,
        toolReviews: [],
        requiredActions: [],
        notices: [],
    },
    {
        productId: "mock-product-8",
        productName: "강아지 자동 급식기 3L",
        productImageUrl: null,
        sourceType: SourceType.Url,
        sourceUrl: "https://detail.1688.com/offer/example-feeder.html",
        sourceText: null,
        imageUrls: [],
        processingStatus: ProcessingStatusType.Failed,
        progresses: [
            { stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.ToolExecution, toolName: ToolName.Electrical, stageStatus: StageStatus.Started },
        ],
        questions: [],
        failure: {
            failedStage: PipelineStage.ToolExecution,
            errorCode: "AI-TIMEOUT",
            errorMessage: "전기 안전 검토 단계에서 응답 시간이 초과되었습니다.",
            retryable: true,
        },
        assessmentStatus: null,
        resultStatus: null,
        summary: null,
        toolReviews: [],
        requiredActions: [],
        notices: [],
    },
    {
        productId: "mock-product-9",
        productName: "전자담배 액상 니코틴 프리 30ml",
        productImageUrl: null,
        sourceType: SourceType.TextImage,
        sourceUrl: null,
        sourceText: "니코틴 프리 전자담배 액상, 30ml",
        imageUrls: [],
        processingStatus: ProcessingStatusType.Failed,
        progresses: [],
        questions: [],
        failure: {
            failedStage: null,
            errorCode: "PRODUCT-RESTRICTED",
            errorMessage: "전자담배 액상은 진단이 불가능한 상품 카테고리입니다.",
            retryable: false,
        },
        assessmentStatus: null,
        resultStatus: null,
        summary: null,
        toolReviews: [],
        requiredActions: [],
        notices: [],
    },
];

// TODO: AI 파이프라인이 연결되면 아래 주석 풀고 목업 대신 실제 API를 쓸 것
// 상품 단건 조회
export async function getProduct(_productId: string) {
    // const response = await apiClient.get(`/api/v1/products/${productId}`);
    // return response.data.data as ProductResult;
    return MOCK_PRODUCT_RESULTS[0];
}

// TODO: AI 파이프라인이 연결되면 아래 주석 풀고 목업 대신 실제 API를 쓸 것
// 진단서 조회 (진단서 단위, 여러 상품 결과를 한 번에 조회)
export const getDiagnosesDetail = async (_diagnosesId: string) => {
    // const response = await apiClient.get(`/api/v1/diagnoses/${diagnosesId}`);
    // return response.data.data.products as ProductResult[];
    return MOCK_PRODUCT_RESULTS;
};
