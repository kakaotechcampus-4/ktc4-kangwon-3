import { type ToolReview, ToolReviewStatus } from "@/api/product";
import SectionIntro from "@/components/common/SectionIntro";
import { type Badge } from "@/constants/statusBadges";
import { cn } from "@/lib/cn";

import { TOOL_NAME_LABELS } from "./constants";
import FindingCard from "./FindingCard";

// 분야별 검토 진행 상태 배지. Skipped는 하단에 따로 노출하므로 매핑하지 않는다.
const TOOL_REVIEW_STATUS_BADGES: Partial<Record<ToolReviewStatus, Badge>> = {
    [ToolReviewStatus.Completed]: { label: "검토 완료", className: "text-neutral-dark bg-white border-neutral-border" },
    [ToolReviewStatus.Incomplete]: { label: "검토 미완료", className: "text-status-warning bg-status-warning-bg" },
};

interface ToolReviewCardProps {
    toolReview: ToolReview
}

function ToolReviewCard({ toolReview }: ToolReviewCardProps) {
    const badge = TOOL_REVIEW_STATUS_BADGES[toolReview.status];

    return (
        <div className="flex w-full flex-col gap-3.5">
            <div className="relative w-full">
                <SectionIntro title={TOOL_NAME_LABELS[toolReview.toolName]} description={toolReview.message ?? ""} size="2xl" />
                {badge && (
                    <div className={cn("absolute top-3 right-3 rounded-full border px-2.5 py-1 text-sm font-semibold", badge.className)}>
                        {badge.label}
                    </div>
                )}
            </div>
            {toolReview.findings.map((finding) => (
                <FindingCard key={finding.productFindingId} finding={finding} />
            ))}
        </div>
    );
}

export default ToolReviewCard;