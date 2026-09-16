type ProcessType = "call" | "act" | "end" | "skip";

interface ProcessProps {
    type: ProcessType;
    title: string;
    job: string;
    detail: string;
    onCorrect?: () => void; // type="skip"일 때 "에이전트 수동 호출" 버튼용
}

const STATUS_ICON_BASE = "h-10 w-10 rounded-full border-2 flex items-center justify-center text-xl";

const STATUS_ICON_VARIANTS: Record<ProcessType, { className: string; mark?: string }> = {
    call: { className: "border-neutral-border animate-soft-ping" },
    act: { className: "border-neutral-border/30 border-t-neutral-border animate-spin" },
    end: { className: "border-primary text-primary animate-pop-in", mark: "✓" },
    skip: { className: "border-neutral-border text-neutral-border", mark: "−" },
};

function StatusIcon({ type }: { type: ProcessType }) {
    const { className, mark } = STATUS_ICON_VARIANTS[type];
    return <div className={`${STATUS_ICON_BASE} ${className}`}>{mark}</div>;
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

                    {type === "skip" && (
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