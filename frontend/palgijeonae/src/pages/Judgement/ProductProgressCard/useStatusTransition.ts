import { useEffect, useState } from "react";

import { ProcessingStatusType } from "@/api/types";

// 진행 중 → 완료 때 막대가 차오르는 시간
const FINISH_MS = 650;

export const isRunningStatus = (status: ProcessingStatusType) =>
    status === ProcessingStatusType.Pending || status === ProcessingStatusType.InProgress;

const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * processingStatus 변화를 감지해 화면에 보여줄 상태와 애니메이션 key를 돌려준다.
 * - 첫 렌더에서는 animationKey가 null이라 효과가 재생되지 않는다.
 * - 진행 중 → 완료일 때는 FINISH_MS 동안 진행 중 화면을 유지하며 막대를 채운다(finishing).
 */
export function useStatusTransition(status: ProcessingStatusType) {
    const [current, setCurrent] = useState(status);
    const [prevStatus, setPrevStatus] = useState<ProcessingStatusType | null>(null);
    const [changeKey, setChangeKey] = useState(0);
    const [finishedKey, setFinishedKey] = useState(0);

    // 렌더 중 상태 조정 패턴 
    if (current !== status) {
        setPrevStatus(current);
        setCurrent(status);
        setChangeKey((key) => key + 1);
    }

    const finishing = changeKey > 0
        && finishedKey !== changeKey
        && prevStatus != null
        && isRunningStatus(prevStatus)
        && status === ProcessingStatusType.Completed
        && !prefersReducedMotion();

    useEffect(() => {
        if (!finishing) return;
        const timer = setTimeout(() => setFinishedKey(changeKey), FINISH_MS);
        return () => clearTimeout(timer);
    }, [finishing, changeKey]);

    return {
        displayStatus: finishing && prevStatus != null ? prevStatus : status,
        finishing,
        animationKey: changeKey > 0 && !finishing ? changeKey : null,
    };
}
