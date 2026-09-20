import type { ProcessType } from "./Process";

// 상태 그룹을 여기 한 곳에서만 정의한다. 새 상태가 추가되면 이 파일만 고치면 된다.
export const TERMINAL_STATUSES: ProcessType[] = ["end", "skip", "fail"];
export const ACTIVE_STATUSES: ProcessType[] = ["call", "act"];
export const CORRECTABLE_STATUSES: ProcessType[] = ["skip", "fail"];

export const isTerminalStatus = (status: ProcessType) => TERMINAL_STATUSES.includes(status);
export const isActiveStatus = (status: ProcessType) => ACTIVE_STATUSES.includes(status);
export const isCorrectableStatus = (status: ProcessType) => CORRECTABLE_STATUSES.includes(status);
