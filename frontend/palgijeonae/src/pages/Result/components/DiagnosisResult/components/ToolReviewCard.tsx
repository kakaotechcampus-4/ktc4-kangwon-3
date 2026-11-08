import { type ToolReview, ToolReviewStatus } from "@/api/types/product";
import SectionIntro from "@/components/common/SectionIntro";
import { cn } from "@/lib/cn";
import { TOOL_NAME_LABELS } from "@/pages/Result/components/DiagnosisResult/constants";
import type { FindingFilter } from "@/pages/Result/components/DiagnosisResult/types";

import FindingCard from "./FindingCard";

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

    // 필터를 적용해서 finding이 비게 된 분야는 숨긴다.
    // 전체 보기에서는 finding이 없어도 분야명·상태·메시지를 보여준다. 정보 부족으로 분야를 확인하지 못해 finding 없이 내려오는 경우에 대비한 안전장치다.
    if (visibleFindings.length === 0 && findingFilter !== null) {
        return null;
    }

    return (
        <div className="flex w-full flex-col gap-5">
            <div className="flex w-full flex-col gap-1 md:relative md:block">
                <SectionIntro title={TOOL_NAME_LABELS[toolReview.toolName]} description={toolReview.message ?? ""} size="2xl" />
                {statusText && (
                    <p className={cn("text-sm font-semibold md:absolute md:top-3 md:right-1", statusText.className)}>
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