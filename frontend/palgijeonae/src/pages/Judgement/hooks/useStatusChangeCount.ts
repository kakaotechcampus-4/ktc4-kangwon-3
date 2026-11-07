import { useState } from "react";

import { ProcessingStatusType } from "@/api/types/common";

// PENDING과 IN_PROGRESS는 화면상 같은 "진행 중"이라 전환으로 치지 않는다.
const toVisualStatus = (status: ProcessingStatusType) =>
    status === ProcessingStatusType.Pending ? ProcessingStatusType.InProgress : status;

/** 화면에 보이는 상태가 바뀔 때마다 1씩 늘어나는 값. 첫 렌더는 0이라 전환 효과가 재생되지 않는다. */
export function useStatusChangeCount(rawStatus: ProcessingStatusType) {
    const status = toVisualStatus(rawStatus);
    const [prevStatus, setPrevStatus] = useState(status);
    const [changeCount, setChangeCount] = useState(0);

    // 렌더 중 상태 조정 패턴
    if (prevStatus !== status) {
        setPrevStatus(status);
        setChangeCount((count) => count + 1);
    }

    return changeCount;
}
