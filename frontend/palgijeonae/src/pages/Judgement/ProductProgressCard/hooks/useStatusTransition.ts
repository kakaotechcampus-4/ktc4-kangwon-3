import { useEffect, useState } from "react";

import { ProcessingStatusType } from "@/api/types";

import { prefersReducedMotion } from "./useAnimateOnChange";

// 진행 중 → 완료 때 막대가 차오르는 시간
const FINISH_MS = 650;

export const isRunningStatus = (status: ProcessingStatusType) =>
    status === ProcessingStatusType.Pending || status === ProcessingStatusType.InProgress;

// PENDING과 IN_PROGRESS는 화면상 같은 "진행 중"이라 전환으로 치지 않는다.
const toVisualStatus = (status: ProcessingStatusType) =>
    status === ProcessingStatusType.Pending ? ProcessingStatusType.InProgress : status;

/**
 * 화면에 보여줄 상태와 전환 효과 트리거를 돌려준다.
 * - changeCount: 화면 상태가 실제로 바뀔 때마다 1씩 증가 (첫 렌더는 0 → 효과 없음)
 * - isFinishing: 진행 중 → 완료 사이 막대가 차오르는 동안 true. 이때 displayStatus는 이전 상태를 유지한다.
 */
export function useStatusTransition(rawStatus: ProcessingStatusType) {
    const status = toVisualStatus(rawStatus);
    const [prevStatus, setPrevStatus] = useState(status);
    const [finishingFrom, setFinishingFrom] = useState<ProcessingStatusType | null>(null);
    const [changeCount, setChangeCount] = useState(0);

    // 렌더 중 상태 조정 패턴
    if (prevStatus !== status) {
        setPrevStatus(status);
        const shouldFinish = isRunningStatus(prevStatus) && status === ProcessingStatusType.Completed && !prefersReducedMotion();
        if (shouldFinish) {
            setFinishingFrom(prevStatus);
        } else {
            setFinishingFrom(null);
            setChangeCount((count) => count + 1);
        }
    }

    // 막대를 다 채우면 완료 화면으로 넘기면서 전환 효과를 재생한다.
    useEffect(() => {
        if (finishingFrom == null) return;
        const timer = setTimeout(() => {
            setFinishingFrom(null);
            setChangeCount((count) => count + 1);
        }, FINISH_MS);
        return () => clearTimeout(timer);
    }, [finishingFrom]);

    return {
        displayStatus: finishingFrom ?? status,
        isFinishing: finishingFrom != null,
        changeCount,
    };
}
