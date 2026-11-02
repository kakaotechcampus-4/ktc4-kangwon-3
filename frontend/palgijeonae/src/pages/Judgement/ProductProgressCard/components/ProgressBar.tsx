import type { ProductProgress } from "@/api/product";
import { PipelineStage } from "@/api/product";
import { cn } from "@/lib/cn";

interface Segment {
    label: string
    stages: PipelineStage[]
}

const PROGRESS_SEGMENTS: Segment[] = [
    { label: "상세페이지 읽기", stages: [PipelineStage.Extraction] },
    { label: "검토 분야 선택", stages: [PipelineStage.Selection] },
    { label: "법령 검토", stages: [PipelineStage.ToolExecution] },
    { label: "정리·검증", stages: [PipelineStage.Aggregation, PipelineStage.Verification, PipelineStage.Finalization] },
];

enum SegmentStatus {
    Completed = "completed",
    Current = "current",
    Upcoming = "upcoming",
}

const BAR_CLASSES: Record<SegmentStatus, string> = {
    [SegmentStatus.Completed]: "bg-primary",
    [SegmentStatus.Current]: "bg-primary opacity-50 motion-safe:animate-segment-breathe",
    [SegmentStatus.Upcoming]: "bg-gray-200",
};

const LABEL_CLASSES: Record<SegmentStatus, string> = {
    [SegmentStatus.Completed]: "font-normal text-neutral-text",
    [SegmentStatus.Current]: "font-bold text-primary",
    [SegmentStatus.Upcoming]: "font-normal text-gray-400",
};

function resolveSegmentStatus(index: number, currentIndex: number): SegmentStatus {
    if (currentIndex === -1 || index > currentIndex) return SegmentStatus.Upcoming;
    return index === currentIndex ? SegmentStatus.Current : SegmentStatus.Completed;
}

interface ProgressBarProps {
    progresses: ProductProgress[]
}

/**
 * 진행 중인 상품의 4단계(상세페이지 읽기/검토 분야 선택/법령 검토/정리·검증) 진행 막대.
 * progresses의 마지막 단계를 기준으로 각 구간을 완료/현재/예정 색으로 표시한다.
 */
function ProgressBar({ progresses }: ProgressBarProps) {
    const currentStage = progresses.at(-1)?.stage;
    const currentIndex = PROGRESS_SEGMENTS.findIndex((segment) => currentStage != null && segment.stages.includes(currentStage));

    return (
        <div className="flex w-full items-start gap-1.5">
            {PROGRESS_SEGMENTS.map((segment, index) => {
                const status = resolveSegmentStatus(index, currentIndex);
                return (
                    <div key={segment.label} className="flex flex-1 flex-col items-start gap-2">
                        <div className={cn("h-1.5 w-full rounded-sm transition-[background-color,opacity] duration-500", BAR_CLASSES[status])} />
                        <p className={cn("text-xs leading-4", LABEL_CLASSES[status])}>
                            {segment.label}
                        </p>
                    </div>
                );
            })}
        </div>
    );
}

export default ProgressBar;
