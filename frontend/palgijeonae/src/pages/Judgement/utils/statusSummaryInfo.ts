import { ProcessingStatusType } from "@/api/types/common";

import { PROCESSING_STATUS_LABELS } from "./processingStatusLabels";

interface StatusSummaryInfo {
    label: string
    dotClassName: string
}

// 요약 바 전용 점 색.
export const STATUS_SUMMARY_INFO: Record<ProcessingStatusType, StatusSummaryInfo> = {
    [ProcessingStatusType.Pending]: { label: PROCESSING_STATUS_LABELS[ProcessingStatusType.Pending], dotClassName: "bg-primary" },
    [ProcessingStatusType.InProgress]: { label: PROCESSING_STATUS_LABELS[ProcessingStatusType.InProgress], dotClassName: "bg-primary" },
    [ProcessingStatusType.AwaitingInput]: { label: PROCESSING_STATUS_LABELS[ProcessingStatusType.AwaitingInput], dotClassName: "bg-status-warning" },
    [ProcessingStatusType.Completed]: { label: PROCESSING_STATUS_LABELS[ProcessingStatusType.Completed], dotClassName: "bg-status-success" },
    [ProcessingStatusType.Failed]: { label: PROCESSING_STATUS_LABELS[ProcessingStatusType.Failed], dotClassName: "bg-status-danger" },
};
