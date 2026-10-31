import type { ProductProgress } from "@/api/product";
import { PipelineStage } from "@/api/product";

const STAGE_DESCRIPTIONS: Record<PipelineStage, string> = {
    [PipelineStage.Extraction]: "상세페이지에서 상품 정보를 읽고 있어요.",
    [PipelineStage.Selection]: "검토할 분야를 고르고 있어요.",
    [PipelineStage.ToolExecution]: "분야별 전문가가 법령을 확인하고 있어요.",
    [PipelineStage.Aggregation]: "검토 결과를 정리하고 있어요.",
    [PipelineStage.Verification]: "검토 결과를 정리하고 있어요.",
    [PipelineStage.Finalization]: "검토 결과를 정리하고 있어요.",
};

const RETRYING_DESCRIPTION = "검증에서 보완할 점이 있어 법령을 다시 확인하고 있어요.";

// 재시도 여부를 알려주는 필드가 없어서, VERIFICATION 이후 TOOL_EXECUTION 재등장으로 판단한다.
function isRetrying(progresses: ProductProgress[]): boolean {
    const verificationIndex = progresses.findIndex((progress) => progress.stage === PipelineStage.Verification);
    if (verificationIndex === -1) {
        return false;
    }
    return progresses.slice(verificationIndex + 1).some((progress) => progress.stage === PipelineStage.ToolExecution);
}

/** 진행 중(InProgress)인 상품 카드에 보여줄 한 줄 설명. */
export function getProgressDescription(progresses: ProductProgress[]): string {
    if (progresses.length === 0) {
        return "진단을 준비하고 있어요.";
    }

    if (isRetrying(progresses)) {
        return RETRYING_DESCRIPTION;
    }

    return STAGE_DESCRIPTIONS[progresses[progresses.length - 1].stage];
}
