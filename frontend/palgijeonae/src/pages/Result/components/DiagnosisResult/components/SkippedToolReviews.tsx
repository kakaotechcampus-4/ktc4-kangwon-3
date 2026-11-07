import type { ToolReview } from "@/api/types/product";
import DefaultBox from "@/components/common/DefaultBox";
import { TOOL_NAME_LABELS } from "@/pages/Result/components/DiagnosisResult/constants";

interface SkippedToolReviewsProps {
    toolReviews: ToolReview[]
}

function SkippedToolReviews({ toolReviews }: SkippedToolReviewsProps) {
    if (toolReviews.length === 0) {
        return null;
    }

    return (
        <DefaultBox variant="dashed" className="bg-white">
            <h2 className="text-base font-bold text-black">검토하지 않은 분야</h2>
            {toolReviews.map((toolReview) => (
                <div key={toolReview.productToolReviewId} className="flex w-full items-start gap-3">
                    <p className="w-30 shrink-0 text-sm font-bold text-neutral-text">{TOOL_NAME_LABELS[toolReview.toolName]}</p>
                    <p className="flex-1 text-sm whitespace-pre-line text-neutral-muted">{toolReview.message}</p>
                </div>
            ))}
        </DefaultBox>
    );
}

export default SkippedToolReviews;
