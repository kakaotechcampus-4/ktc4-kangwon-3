import { cn } from "@/lib/cn";

enum DotState {
    Complete = "complete",
    Answered = "answered",
    Unanswered = "unanswered",
}

// 질문별 답변 상태를 나타내는 점 색
const DOT_STATE_CLASSES: Record<DotState, string> = {
    [DotState.Complete]: "bg-status-success",
    [DotState.Answered]: "bg-primary",
    [DotState.Unanswered]: "bg-neutral-200",
};

interface ProgressSummaryProps {
    currentAnswered: boolean[] // 현재 상품의 질문들에 대한 답변 여부
}

function ProgressSummary({ currentAnswered }: ProgressSummaryProps) {
    const answeredCount = currentAnswered.filter(Boolean).length;
    const totalCount = currentAnswered.length;
    const isComplete = totalCount > 0 && answeredCount === totalCount;
    const dotStates = currentAnswered.map((answered) => isComplete ? DotState.Complete : answered ? DotState.Answered : DotState.Unanswered);

    return (
        <div className="flex flex-wrap items-center gap-2.5 rounded-[10px] bg-neutral-50 px-4 py-3 text-sm text-neutral-dark">
            <div aria-hidden="true" className="flex gap-1">
                {dotStates.map((dotState, index) => (
                    <span
                        key={index}
                        className={cn("size-2 rounded-full", DOT_STATE_CLASSES[dotState])}
                    />
                ))}
            </div>
            {isComplete ? (
                <span><b className="font-semibold text-status-success">답변 완료</b></span>
            ) : (
                <span><b className="font-semibold text-black">{answeredCount}/{totalCount}</b> 답변</span>
            )}
        </div>
    );
}

export default ProgressSummary;
