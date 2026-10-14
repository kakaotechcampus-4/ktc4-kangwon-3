import { ProcessType } from "./types";

// 상태 그룹을 여기 한 곳에서만 정의한다. 새 상태가 추가되면 이 파일만 고치면 된다.
export const TERMINAL_STATUSES: ProcessType[] = [ProcessType.End, ProcessType.Skip, ProcessType.Fail];
export const ACTIVE_STATUSES: ProcessType[] = [ProcessType.Call, ProcessType.Act];
export const CORRECTABLE_STATUSES: ProcessType[] = [ProcessType.Skip, ProcessType.Fail];

export const isTerminalStatus = (status: ProcessType) => TERMINAL_STATUSES.includes(status);
export const isActiveStatus = (status: ProcessType) => ACTIVE_STATUSES.includes(status);
export const isCorrectableStatus = (status: ProcessType) => CORRECTABLE_STATUSES.includes(status);
