import { ProcessingStatusType } from "@/api/types";
import { cn } from "@/lib/cn";

import { useAnimateOnChange } from "../hooks/useAnimateOnChange";

const FLASH_BG: Record<ProcessingStatusType, string> = {
    [ProcessingStatusType.Pending]: "bg-primary/10",
    [ProcessingStatusType.InProgress]: "bg-primary/10",
    [ProcessingStatusType.AwaitingInput]: "bg-status-warning-bg",
    [ProcessingStatusType.Completed]: "bg-status-success-bg",
    [ProcessingStatusType.Failed]: "bg-status-danger-bg",
};

// 컴포넌트 안에서 만들면 렌더마다 새 배열/객체가 생겨 useAnimateOnChange의 effect가 매번 다시 실행된다
const FLASH_KEYFRAMES: Keyframe[] = [{ opacity: 1 }, { opacity: 0 }];
const FLASH_OPTIONS: KeyframeAnimationOptions = { duration: 1200, easing: "ease-out" };

interface StatusFlashProps {
    status: ProcessingStatusType
    trigger: number
}

/** 상태가 바뀐 순간 카드 배경에 상태색을 잠깐 깔았다가 걷어낸다. 평소엔 투명. */
function StatusFlash({ status, trigger }: StatusFlashProps) {
    const ref = useAnimateOnChange<HTMLSpanElement>(trigger, FLASH_KEYFRAMES, FLASH_OPTIONS);

    return <span ref={ref} aria-hidden="true" className={cn("pointer-events-none absolute inset-0 opacity-0", FLASH_BG[status])} />;
}

export default StatusFlash;
