import type { ProductProgress } from "@/api/product";
import { PipelineStage } from "@/api/product";
import { cn } from "@/lib/cn";

interface Segment {
    label: string
    // 하나의 구간에 여러 단계가 합쳐질 수 있다 (정리·검증 = 집계/검증/최종화).
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
    // 진행 중 → 완료로 넘어가며 초록으로 채워지는 중
    Finished = "finished",
}

const BAR_CLASSES: Record<SegmentStatus, string> = {
    [SegmentStatus.Completed]: "bg-primary",
    [SegmentStatus.Current]: "bg-primary opacity-50 motion-safe:animate-segment-breathe",
    [SegmentStatus.Upcoming]: "bg-gray-200",
    [SegmentStatus.Finished]: "bg-status-success opacity-100 duration-250",
};

const LABEL_CLASSES: Record<SegmentStatus, string> = {
    [SegmentStatus.Completed]: "font-normal text-neutral-text",
    [SegmentStatus.Current]: "font-bold text-primary",
    [SegmentStatus.Upcoming]: "font-normal text-gray-400",
    [SegmentStatus.Finished]: "font-normal text-status-success",
};

function resolveSegmentStatus(index: number, currentIndex: number): SegmentStatus {
    if (currentIndex === -1 || index > currentIndex) return SegmentStatus.Upcoming;
    return index === currentIndex ? SegmentStatus.Current : SegmentStatus.Completed;
}

interface ProgressBarProps {
    progresses: ProductProgress[]
    // 진행 중 → 완료로 넘어가는 중이면 남은 막대를 순서대로 채운다.
    finishing?: boolean
}

function ProgressBar({ progresses, finishing = false }: ProgressBarProps) {
    const currentStage = progresses.at(-1)?.stage;
    const currentIndex = PROGRESS_SEGMENTS.findIndex((segment) => currentStage != null && segment.stages.includes(currentStage));

    return (
        <div className="flex w-full items-start gap-1.5">
            {PROGRESS_SEGMENTS.map((segment, index) => {
                const status = finishing ? SegmentStatus.Finished : resolveSegmentStatus(index, currentIndex);
                return (
                    <div key={segment.label} className="flex flex-1 flex-col items-start gap-2">
                        <div
                            className={cn("h-1.5 w-full rounded-sm transition-[background-color,opacity] duration-500", BAR_CLASSES[status])}
                            style={finishing ? { transitionDelay: `${index * 80}ms` } : undefined}
                        />
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
