import { type DiagnosesDetail, PipelineStage, StageStatus, ToolName } from "@/api/product";
import { ProcessingStatusType, ResultStatus, SourceType } from "@/api/types";

// TEMP: UI 구현을 위한 목업 데이터. 상품마다 진행 속도가 다른 상황(진행 중/질문 대기/완료)을 함께 보여준다.
// TODO: AI 파이프라인이 연결되면 일괄 제거한다.
const MOCK_DIAGNOSES_DETAIL: DiagnosesDetail = {
    diagnosesId: "mock-diagnoses-1",
    processingStatus: ProcessingStatusType.InProgress,
    pollIntervalMs: 3000,
    products: [
        {
            productId: "mock-judgement-product-1",
            diagnosesId: "mock-diagnoses-1",
            productName: "블루투스 5.3 무선 이어폰 TWS 충전케이스 포함",
            productImageUrl: null,
            sourceType: SourceType.Url,
            sourceUrl: "https://detail.1688.com/offer/example-earbuds.html",
            sourceText: null,
            imageUrls: [],
            processingStatus: ProcessingStatusType.InProgress,
            progresses: [
                { stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Completed },
                { stage: PipelineStage.Selection, toolName: null, stageStatus: StageStatus.Completed },
                { stage: PipelineStage.ToolExecution, toolName: ToolName.Radio, stageStatus: StageStatus.Started },
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
            productId: "mock-judgement-product-2",
            diagnosesId: "mock-diagnoses-1",
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
                    questionId: "mock-judgement-question-2-1",
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
            productId: "mock-judgement-product-3",
            diagnosesId: "mock-diagnoses-1",
            productName: "무선 미니 가습기 USB 충전식",
            productImageUrl: null,
            sourceType: SourceType.TextImage,
            sourceUrl: null,
            sourceText: "USB로 충전하는 무선 미니 가습기",
            imageUrls: [],
            processingStatus: ProcessingStatusType.InProgress,
            progresses: [
                { stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Completed },
                { stage: PipelineStage.Selection, toolName: null, stageStatus: StageStatus.Completed },
                { stage: PipelineStage.ToolExecution, toolName: ToolName.Electrical, stageStatus: StageStatus.Started },
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
            productId: "mock-judgement-product-4",
            diagnosesId: "mock-diagnoses-1",
            productName: "접이식 캠핑 테이블 알루미늄",
            productImageUrl: null,
            sourceType: SourceType.Url,
            sourceUrl: "https://detail.1688.com/offer/example-camping-table.html",
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
    ],
    createdAt: "2026-10-30T12:00:00",
    updatedAt: "2026-10-30T12:05:00",
};

// TEMP: 실제 숏폴링처럼 호출할 때마다 진행 상태가 바뀌는 것처럼 보여주는 임시 목업. 삭제 예정.
let mockPollTick = 0;

// TEMP: 틱이 지날수록 상품마다 다른 속도로 진행되다가, 마지막엔 모두 끝나서 진단서 전체도 끝난다.
function buildMockSnapshot(tick: number): DiagnosesDetail {
    const snapshot = structuredClone(MOCK_DIAGNOSES_DETAIL);
    const [product1, product2, product3, product4] = snapshot.products;

    if (tick >= 1) {
        product1.progresses = [
            { stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.Selection, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.ToolExecution, toolName: ToolName.Radio, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.Aggregation, toolName: null, stageStatus: StageStatus.Started },
        ];

        product3.processingStatus = ProcessingStatusType.Completed;
        product3.progresses = [
            { stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.Selection, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.ToolExecution, toolName: ToolName.Electrical, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.Aggregation, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.Finalization, toolName: null, stageStatus: StageStatus.Completed },
        ];
        product3.resultStatus = ResultStatus.PurchasingAgentAllowed;
        product3.summary = "구매대행으로 판매 가능한 상품입니다.";

        product4.progresses = [
            { stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.Selection, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.ToolExecution, toolName: ToolName.Customs, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.Aggregation, toolName: null, stageStatus: StageStatus.Completed },
            { stage: PipelineStage.Verification, toolName: null, stageStatus: StageStatus.Started },
        ];
    }

    if (tick >= 2) {
        product1.processingStatus = ProcessingStatusType.Completed;
        product1.progresses.push({ stage: PipelineStage.Finalization, toolName: null, stageStatus: StageStatus.Completed });
        product1.resultStatus = ResultStatus.PurchasingAgentAllowed;
        product1.summary = "구매대행으로 판매 가능한 상품입니다.";

        product2.processingStatus = ProcessingStatusType.Completed;
        product2.questions[0].answerText = "구매대행으로 판매할 예정이에요.";
        product2.resultStatus = ResultStatus.RecheckRequired;
        product2.summary = "일부 조건을 다시 확인해야 해요.";

        product4.processingStatus = ProcessingStatusType.Failed;
        product4.failure = {
            failedStage: PipelineStage.Verification,
            errorCode: "TOOL_TIMEOUT",
            errorMessage: "검증 중 응답 시간이 초과됐어요. 잠시 후 다시 시도해 주세요.",
            retryable: true,
        };

        snapshot.processingStatus = ProcessingStatusType.Completed;
        snapshot.pollIntervalMs = null;
    }

    return snapshot;
}

// TODO: AI 파이프라인이 연결되면 아래 주석 풀고 목업 대신 실제 API를 쓸 것
export async function getDiagnosesPolling(_diagnosesId: string) {
    // const response = await apiClient.get(`/api/v1/diagnoses/${diagnosesId}`);
    // return response.data.data as DiagnosesDetail;
    const snapshot = buildMockSnapshot(mockPollTick);
    mockPollTick += 1;
    return snapshot;
}
