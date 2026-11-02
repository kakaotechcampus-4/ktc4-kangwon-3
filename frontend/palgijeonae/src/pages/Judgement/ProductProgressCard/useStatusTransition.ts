import { useEffect, useState } from "react";

import { ProcessingStatusType } from "@/api/types";

// 진행 중 → 완료 때 막대가 차오르는 시간
const FINISH_MS = 650;

export const isRunningStatus = (status: ProcessingStatusType) =>
    status === ProcessingStatusType.Pending || status === ProcessingStatusType.InProgress;

const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// 화면에는 PENDING과 IN_PROGRESS가 똑같이 "진행 중"으로 보이니, 둘 사이를 오가는 건 전환으로 치지 않는다.
const toVisualStatus = (status: ProcessingStatusType) =>
    status === ProcessingStatusType.Pending ? ProcessingStatusType.InProgress : status;

/**
 * processingStatus 변화를 감지해 화면에 보여줄 상태와 애니메이션 key를 돌려준다.
 * - 첫 렌더에서는 animationKey가 null이라 효과가 재생되지 않는다.
 * - 진행 중 → 완료일 때는 FINISH_MS 동안 진행 중 화면을 유지하며 막대를 채운다(finishing).
 * - contentKey는 finishing 동안 이전 값을 유지한다. 그래야 콘텐츠가 리마운트되지 않고
 *   ProgressBar가 같은 엘리먼트로 남아 색 전환 트랜지션이 재생된다.
 */
export function useStatusTransition(rawStatus: ProcessingStatusType) {
    const status = toVisualStatus(rawStatus);
    const [current, setCurrent] = useState(status);
    const [prevStatus, setPrevStatus] = useState<ProcessingStatusType | null>(null);
    const [changeKey, setChangeKey] = useState(0);
    const [committedKey, setCommittedKey] = useState(0);

    // 렌더 중 상태 조정 패턴
    if (current !== status) {
        const willFinish = isRunningStatus(current) && status === ProcessingStatusType.Completed && !prefersReducedMotion();
        const nextChangeKey = changeKey + 1;
        setPrevStatus(current);
        setCurrent(status);
        setChangeKey(nextChangeKey);
        // finishing으로 이어지지 않는 전환만 즉시 커밋한다. finishing이면 타이머가 끝난 뒤 커밋된다.
        if (!willFinish) {
            setCommittedKey(nextChangeKey);
        }
    }

    const finishing = changeKey > 0 && committedKey !== changeKey;

    useEffect(() => {
        if (!finishing) return;
        const timer = setTimeout(() => setCommittedKey(changeKey), FINISH_MS);
        return () => clearTimeout(timer);
    }, [finishing, changeKey]);

    return {
        displayStatus: finishing && prevStatus != null ? prevStatus : status,
        finishing,
        animationKey: changeKey > 0 && !finishing ? changeKey : null,
        contentKey: committedKey,
    };
}
