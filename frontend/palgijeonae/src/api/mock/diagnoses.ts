import { MOCK_DIAGNOSES_DETAIL } from "@/api/mock/data/diagnosesDetail";
import { MOCK_PRODUCT_RESULTS } from "@/api/mock/data/productResults";
import { ProcessingStatusType, ResultStatus } from "@/api/types/common";
import { type DiagnosesDetail, PipelineStage, type ProductResult, StageStatus, ToolName } from "@/api/types/product";

/**
 * 로컬에서 BE 없이 테스트할 때만 쓰는 픽스처.
 * 쓰려면 호출부의 import를 "@/api/diagnoses" 대신 "@/api/mock/diagnoses"로 바꾸면 된다.
 */

/** 개발용 진단서 조회 함수 (진단서 단위, 여러 상품 결과를 한 번에 조회) */
export async function getDiagnosesDetail(_diagnosesId: string): Promise<ProductResult[]> {
    return MOCK_PRODUCT_RESULTS;
}

/** 폴링 호출마다 늘어나는 진행 tick. diagnosesId가 바뀌면 처음부터 다시 센다. */
let mockPollTick = 0;
let mockPollDiagnosesId: string | null = null;

/** 개발용 진단 상태 폴링 함수 */
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

/** 개발용 진단 상태 폴링 함수 */
export async function getDiagnosesPolling(diagnosesId: string) {
    if (diagnosesId !== mockPollDiagnosesId) {
        mockPollDiagnosesId = diagnosesId;
        mockPollTick = 0;
    }
    const snapshot = buildMockSnapshot(mockPollTick);
    mockPollTick += 1;
    return snapshot;
}
