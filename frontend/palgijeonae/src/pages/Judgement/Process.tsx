import { cva } from "class-variance-authority";

import { isCorrectableStatus } from "./processStatus";

export type ProcessType = "call" | "act" | "end" | "skip" | "fail";

interface ProcessProps {
    type: ProcessType;
    title: string;
    job: string;
    detail: string;
    onCorrect?: () => void; // type="skip" | "fail"일 때 "수동으로 에이전트 호출" 버튼용
}

const statusIconVariants = cva("h-10 w-10 rounded-full border-2 flex items-center justify-center text-xl", {
    variants: {
        type: {
            call: "border-neutral-border animate-soft-ping",
            act: "border-neutral-border/30 border-t-neutral-border animate-spin",
            end: "border-primary text-primary animate-pop-in",
            skip: "border-neutral-border text-neutral-border",
            fail: "border-red-500 text-red-500",
        },
    },
});

// 아이콘 안에 들어갈 문자는 스타일(cva)이 아니라 콘텐츠라 별도로 관리한다.
const STATUS_MARKS: Partial<Record<ProcessType, string>> = {
    end: "✓",
    skip: "−",
    fail: "✕",
};

function StatusIcon({ type }: { type: ProcessType }) {
    return <div className={statusIconVariants({ type })}>{STATUS_MARKS[type]}</div>;
}

function Process({ type, title, job, detail, onCorrect }: ProcessProps) {
    return (
        <div className="rounded-lg border border-neutral-border p-4 transition-colors">
            <div className="flex items-start gap-7">
                <div className="mt-0.5 shrink-0">
                    <StatusIcon type={type} />
                </div>
                <div className="flex flex-1 flex-col items-start gap-1">
                    <p className="text-xl font-semibold text-neutral-text">{title}</p>
                    <p className="text-sm font-medium text-neutral-dark">{job}</p>
                    <p className="text-base text-neutral-muted">{detail}</p>

                    {isCorrectableStatus(type) && (
                        <button
                            onClick={onCorrect}
                            className="mt-2 text-sm border border-neutral-border rounded-md px-3 py-1 text-neutral-dark hover:bg-neutral-border/10"
                        >
                            수동으로 에이전트 호출
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}

export default Process;