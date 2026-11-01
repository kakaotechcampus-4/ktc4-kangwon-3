import { ProcessingStatusType } from "@/api/types";
import { cn } from "@/lib/cn";

// 진행 카드 전용 배지. Result 페이지의 PROCESSING_STATUS_BADGES와 달리 상태별 색을 입힌다.
const PROGRESS_STATUS_BADGE: Record<ProcessingStatusType, { label: string, className: string }> = {
    [ProcessingStatusType.Pending]: { label: "진행 중", className: "border-primary bg-[#eaf0ff] text-primary" },
    [ProcessingStatusType.InProgress]: { label: "진행 중", className: "border-primary bg-[#eaf0ff] text-primary" },
    [ProcessingStatusType.AwaitingInput]: { label: "답변 필요", className: "border-status-warning bg-status-warning-bg text-[#6e500b]" },
    [ProcessingStatusType.Completed]: { label: "완료", className: "border-status-success bg-status-success-bg text-status-success" },
    [ProcessingStatusType.Failed]: { label: "실패", className: "border-status-danger bg-status-danger-bg text-status-danger" },
};

interface StatusBadgeProps {
    processingStatus: ProcessingStatusType
}

function StatusBadge({ processingStatus }: StatusBadgeProps) {
    const badge = PROGRESS_STATUS_BADGE[processingStatus];

    return (
        <div className={cn("rounded-full border px-3 py-1 text-sm font-medium", badge.className)}>
            {badge.label}
        </div>
    );
}

export default StatusBadge;
