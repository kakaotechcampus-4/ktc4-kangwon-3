import { ProcessingStatusType } from "@/api/types";

interface StatusSummaryInfo {
    label: string
    dotClassName: string
}

// 요약 바 전용 라벨/점 색.
export const STATUS_SUMMARY_INFO: Record<ProcessingStatusType, StatusSummaryInfo> = {
    [ProcessingStatusType.Pending]: { label: "진행 중", dotClassName: "bg-primary" },
    [ProcessingStatusType.InProgress]: { label: "진행 중", dotClassName: "bg-primary" },
    [ProcessingStatusType.AwaitingInput]: { label: "답변 필요", dotClassName: "bg-status-warning" },
    [ProcessingStatusType.Completed]: { label: "완료", dotClassName: "bg-status-success" },
    [ProcessingStatusType.Failed]: { label: "실패", dotClassName: "bg-status-danger" },
};
