import { ProcessingStatusType } from "@/api/types";

// PENDING도 화면에서는 진행 중으로 보여준다.
export const isRunningStatus = (status: ProcessingStatusType) =>
    status === ProcessingStatusType.Pending || status === ProcessingStatusType.InProgress;
