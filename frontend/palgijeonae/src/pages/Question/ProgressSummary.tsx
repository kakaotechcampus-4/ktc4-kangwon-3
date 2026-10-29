import { cva } from "class-variance-authority";

// 질문별 답변 상태를 나타내는 점 스타일
const dotVariants = cva("size-2 rounded-full", {
    variants: {
        state: {
            complete: "bg-status-success",
            answered: "bg-primary",
            unanswered: "bg-neutral-200",
        },
    },
});

interface ProgressSummaryProps {
    currentAnswered: boolean[] // 현재 상품의 질문들에 대한 답변 여부
}

function ProgressSummary({ currentAnswered }: ProgressSummaryProps) {
    const answeredCount = currentAnswered.filter(Boolean).length;
    const totalCount = currentAnswered.length;
    const isComplete = totalCount > 0 && answeredCount === totalCount;

    return (
        <div className="flex flex-wrap items-center gap-2.5 rounded-[10px] bg-neutral-50 px-4 py-3 text-sm text-neutral-dark">
            <div aria-hidden="true" className="flex gap-1">
                {currentAnswered.map((answered, index) => (
                    <span
                        key={index}
                        className={dotVariants({
                            state: isComplete ? "complete" : answered ? "answered" : "unanswered",
                        })}
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
