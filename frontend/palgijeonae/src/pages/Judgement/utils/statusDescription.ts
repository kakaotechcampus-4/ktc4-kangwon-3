import type { ProductProgress, ProductResult } from "@/api/product";
import { PipelineStage } from "@/api/product";
import { ProcessingStatusType } from "@/api/types";
import { getCurrentRoundQuestions } from "@/lib/questions";

const STAGE_DESCRIPTIONS: Record<PipelineStage, string> = {
    [PipelineStage.Extraction]: "상세페이지에서 상품 정보를 읽고 있어요.",
    [PipelineStage.Selection]: "검토할 분야를 고르고 있어요.",
    [PipelineStage.ToolExecution]: "분야별 전문가가 법령을 확인하고 있어요.",
    [PipelineStage.Aggregation]: "검토 결과를 정리하고 있어요.",
    [PipelineStage.Verification]: "검토 결과를 정리하고 있어요.",
    [PipelineStage.Finalization]: "검토 결과를 정리하고 있어요.",
};

const RETRYING_DESCRIPTION = "검증에서 보완할 점이 있어 법령을 다시 확인하고 있어요.";

/**
 * 법령 재검토 여부를 알려주는 필드가 없어서, VERIFICATION 이후 TOOL_EXECUTION 재등장으로 판단한다.
 * (AI 파이프라인에서 재시도 가능한 단계는 법령 검토뿐이다)
 */
function isRetrying(progresses: ProductProgress[]): boolean {
    const verificationIndex = progresses.findIndex((progress) => progress.stage === PipelineStage.Verification);
    if (verificationIndex === -1) {
        return false;
    }
    return progresses.slice(verificationIndex + 1).some((progress) => progress.stage === PipelineStage.ToolExecution);
}

/** 진행 중(또는 대기 중, PENDING도 같은 방식으로 보여준다)인 상품의 설명. */
function getProgressDescription(progresses: ProductProgress[]): string {
    if (progresses.length === 0) {
        return "진단을 준비하고 있어요.";
    }

    if (isRetrying(progresses)) {
        return RETRYING_DESCRIPTION;
    }

    return STAGE_DESCRIPTIONS[progresses[progresses.length - 1].stage];
}

/** 카드에 보여줄 상태 설명 한 줄. */
export function getStatusDescription(product: ProductResult): string {
    switch (product.processingStatus) {
        // PENDING은 AI 서버가 요청을 못 받아 재요청을 기다리는 중 — IN_PROGRESS와 동일하게 보여준다.
        case ProcessingStatusType.Pending:
        case ProcessingStatusType.InProgress:
            return getProgressDescription(product.progresses);
        case ProcessingStatusType.AwaitingInput:
            return `확인이 필요한 질문 ${getCurrentRoundQuestions(product.questions).length}개`;
        case ProcessingStatusType.Completed:
            return product.summary ?? "진단이 완료되었어요.";
        case ProcessingStatusType.Failed:
            return product.failure?.errorMessage ?? "진단에 실패했어요.";
    }
}
