import { ProcessingStatusType } from "@/api/types";
import { cn } from "@/lib/cn";

import { PROCESSING_STATUS_LABELS } from "../utils/processingStatusLabels";

// 진행 카드 전용 배지 색.
const PROGRESS_STATUS_BADGE_CLASSNAME: Record<ProcessingStatusType, string> = {
    [ProcessingStatusType.Pending]: "border-primary bg-primary/10 text-primary",
    [ProcessingStatusType.InProgress]: "border-primary bg-primary/10 text-primary",
    [ProcessingStatusType.AwaitingInput]: "border-status-warning bg-status-warning-bg text-status-warning",
    [ProcessingStatusType.Completed]: "border-status-success bg-status-success-bg text-status-success",
    [ProcessingStatusType.Failed]: "border-status-danger bg-status-danger-bg text-status-danger",
};

interface StatusBadgeProps {
    processingStatus: ProcessingStatusType
}

/** 진행 카드 상단에 붙는 상태 배지. 진행 중/답변 필요/완료/실패를 색으로 구분해 보여준다. */
function StatusBadge({ processingStatus }: StatusBadgeProps) {
    return (
        <div className={cn("shrink-0 rounded-full border px-3 py-1 text-sm font-medium whitespace-nowrap", PROGRESS_STATUS_BADGE_CLASSNAME[processingStatus])}>
            {PROCESSING_STATUS_LABELS[processingStatus]}
        </div>
    );
}

export default StatusBadge;
