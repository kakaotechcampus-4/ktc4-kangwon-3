import { type ToolReview, ToolReviewStatus } from "@/api/product";
import SectionIntro from "@/components/common/SectionIntro";
import { cn } from "@/lib/cn";

import { TOOL_NAME_LABELS } from "./constants";
import FindingCard from "./FindingCard";
import type { FindingFilter } from "./FindingFilterBar";

interface ToolReviewStatusText {
    label: string
    className: string
}

// 분야별 검토 진행 상태 표시.
const TOOL_REVIEW_STATUS_TEXT: Partial<Record<ToolReviewStatus, ToolReviewStatusText>> = {
    [ToolReviewStatus.Completed]: { label: "✔ 검토 완료", className: "text-status-success" },
    [ToolReviewStatus.Incomplete]: { label: "✖ 검토 미완료", className: "text-status-danger" },
};

interface ToolReviewCardProps {
    toolReview: ToolReview
    findingFilter: FindingFilter
}

function ToolReviewCard({ toolReview, findingFilter }: ToolReviewCardProps) {
    const statusText = TOOL_REVIEW_STATUS_TEXT[toolReview.status];

    // determination으로 finding을 필터링
    const visibleFindings = toolReview.findings.filter(
        (finding) => findingFilter === null || finding.determination === findingFilter,
    );

    // 필터링된 finding 항목이 없다면 표시하지 않음
    if (visibleFindings.length === 0) {
        return null;
    }

    return (
        <div className="flex w-full flex-col gap-3.5">
            <div className="relative w-full">
                <SectionIntro title={TOOL_NAME_LABELS[toolReview.toolName]} description={toolReview.message ?? ""} size="2xl" />
                {statusText && (
                    <p className={cn("absolute top-3 right-1 text-sm font-semibold", statusText.className)}>
                        {statusText.label}
                    </p>
                )}
            </div>
            {visibleFindings.map((finding) => (
                <FindingCard key={finding.productFindingId} finding={finding} />
            ))}
        </div>
    );
}

export default ToolReviewCard;