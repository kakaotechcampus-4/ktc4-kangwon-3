import { cva } from "class-variance-authority";

// 상품별 질문 진행 상태를 나타내는 점 스타일
const dotVariants = cva("size-2 rounded-full", {
    variants: {
        state: {
            complete: "bg-status-success",
            answered: "bg-primary",
            unanswered: "bg-neutral-200",
        },
    },
});

// 전체 상품별 질문 진행 상태를 나타내는 세그먼트 스타일
const segmentVariants = cva("h-1.5 w-5 rounded-full", {
    variants: {
        state: {
            complete: "bg-status-success",
            partial: "bg-primary/35",
            empty: "bg-neutral-200",
        },
    },
});

interface ProgressSummaryProps {
    currentAnswered: boolean[] // 현재 선택된 제품의 질문들에 대한 답변 여부
    productRatios: number[] // 각 제품별 답변 완료 비율 (0~1)
}

function ProgressSummary({ currentAnswered, productRatios }: ProgressSummaryProps) {
    // 현재 선택된 제품의 질문들에 대한 답변 여부
    const answeredCount = currentAnswered.filter(Boolean).length;
    const totalCount = currentAnswered.length;
    const isCurrentComplete = totalCount > 0 && answeredCount === totalCount;

    // 전체 제품에 대한 답변 완료 여부
    const completedProductCount = productRatios.filter((ratio) => ratio === 1).length;
    const totalProductCount = productRatios.length;
    const isAllComplete = totalProductCount > 0 && completedProductCount === totalProductCount;

    return (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-[10px] bg-neutral-50 px-4 py-3 text-sm text-neutral-dark">
            <div className="flex items-center gap-2.5">
                <p>현재 제품</p>
                <div aria-hidden="true" className="flex gap-1">
                    {currentAnswered.map((answered, index) => (
                        <span
                            key={index}
                            className={dotVariants({
                                state: isCurrentComplete ? "complete" : answered ? "answered" : "unanswered",
                            })}
                        />
                    ))}
                </div>
                {isCurrentComplete ? (
                    <span><b className="font-semibold text-status-success">답변 완료</b></span>
                ) : (
                    <span><b className="font-semibold text-black">{answeredCount}/{totalCount}</b> 답변</span>
                )}
            </div>
            <div className="flex items-center gap-2.5">
                <p>전체 제품</p>
                <div aria-hidden="true" className="flex gap-0.75">
                    {productRatios.map((ratio, index) => (
                        <span
                            key={index}
                            className={segmentVariants({
                                state: ratio === 1 ? "complete" : ratio > 0 ? "partial" : "empty",
                            })}
                        />
                    ))}
                </div>
                {isAllComplete ? (
                    <span><b className="font-semibold text-status-success">답변 완료</b></span>
                ) : (
                    <span><b className="font-semibold text-black">{completedProductCount}/{totalProductCount}</b> 제품 완료</span>
                )}
            </div>
        </div>
    );
}

export default ProgressSummary;
