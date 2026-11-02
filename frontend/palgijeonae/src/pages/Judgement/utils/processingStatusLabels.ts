import { ProcessingStatusType } from "@/api/types";

// 진행 카드 배지·요약 바에서 공통으로 쓰는 상태 라벨. PENDING은 화면에서 IN_PROGRESS와 같은 "진행 중"으로 보여준다.
export const PROCESSING_STATUS_LABELS: Record<ProcessingStatusType, string> = {
    [ProcessingStatusType.Pending]: "진행 중",
    [ProcessingStatusType.InProgress]: "진행 중",
    [ProcessingStatusType.AwaitingInput]: "답변 필요",
    [ProcessingStatusType.Completed]: "완료",
    [ProcessingStatusType.Failed]: "실패",
};
