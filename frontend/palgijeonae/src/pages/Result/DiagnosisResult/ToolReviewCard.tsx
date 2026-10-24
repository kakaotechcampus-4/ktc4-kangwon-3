import { ToolName, type ToolReview } from "@/api/product";
import SectionIntro from "@/components/common/SectionIntro";

import FindingCard from "./FindingCard";

const TOOL_NAME_LABELS: Record<ToolName, string> = {
    [ToolName.Customs]: "통관",
    [ToolName.Children]: "어린이 제품",
    [ToolName.Electrical]: "전기 안전",
    [ToolName.Radio]: "전파",
    [ToolName.FoodDrug]: "식약",
    [ToolName.LabelAd]: "표시 광고",
};

interface ToolReviewCardProps {
    toolReview: ToolReview
}

function ToolReviewCard({ toolReview }: ToolReviewCardProps) {
    return (
        <div className="flex w-full flex-col gap-3.5">
            <SectionIntro title={TOOL_NAME_LABELS[toolReview.toolName]} size="2xl" />
            {toolReview.message && (
                <p className="text-sm leading-relaxed text-neutral-muted">{toolReview.message}</p>
            )}
            {toolReview.findings.map((finding) => (
                <FindingCard key={finding.productFindingId} finding={finding} />
            ))}
        </div>
    );
}

export default ToolReviewCard;