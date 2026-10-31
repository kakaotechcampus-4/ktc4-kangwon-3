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
            processingStatus: ProcessingStatusType.Completed,
            progresses: [
                { stage: PipelineStage.Extraction, toolName: null, stageStatus: StageStatus.Completed },
                { stage: PipelineStage.Selection, toolName: null, stageStatus: StageStatus.Completed },
                { stage: PipelineStage.ToolExecution, toolName: null, stageStatus: StageStatus.Completed },
                { stage: PipelineStage.Aggregation, toolName: null, stageStatus: StageStatus.Completed },
                { stage: PipelineStage.Finalization, toolName: null, stageStatus: StageStatus.Completed },
            ],
            questions: [],
            failure: null,
            assessmentStatus: null,
            resultStatus: ResultStatus.PurchasingAgentAllowed,
            summary: "구매대행으로 판매 가능한 상품입니다.",
            toolReviews: [],
            requiredActions: [],
            notices: [],
        },
    ],
    createdAt: "2026-10-30T12:00:00",
    updatedAt: "2026-10-30T12:05:00",
};

// TODO: AI 파이프라인이 연결되면 아래 주석 풀고 목업 대신 실제 API를 쓸 것
// 진단서 조회(숏폴링). Judgement 페이지 전용 — Result 페이지가 쓰는 getDiagnosesDetail과 달리 pollIntervalMs를 함께 반환한다.
export async function getDiagnosesPolling(_diagnosesId: string) {
    // const response = await apiClient.get(`/api/v1/diagnoses/${diagnosesId}`);
    // return response.data.data as DiagnosesDetail;
    return MOCK_DIAGNOSES_DETAIL;
}
