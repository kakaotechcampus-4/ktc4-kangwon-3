import { type ProductResult, ToolReviewStatus } from "@/api/product";
import { ResultStatus } from "@/api/types";
import { FALLBACK_BADGE, RESULT_STATUS_BADGES } from "@/constants/statusBadges";

import ResultBanner from "./ResultBanner";
import SkippedToolReviews from "./SkippedToolReviews";
import ToolReviewCard from "./ToolReviewCard";

interface DiagnosisResultTabProps {
    product: ProductResult
    onNextStepsClick: () => void
}

function DiagnosisResultTab({ product, onNextStepsClick }: DiagnosisResultTabProps) {
    const { resultStatus, summary, requiredActions, toolReviews } = product;
    const visibleToolReviews = toolReviews.filter((toolReview) => toolReview.status !== ToolReviewStatus.Skipped);
    const skippedToolReviews = toolReviews.filter((toolReview) => toolReview.status === ToolReviewStatus.Skipped);
    const statusLabel = resultStatus ? RESULT_STATUS_BADGES[resultStatus].label : FALLBACK_BADGE.label;

    // 성공했거나, 진단 결과가 없을 때는 해야할 일 건수를 숨김
    const hideRequiredActionsCount = resultStatus === ResultStatus.PurchasingAgentAllowed || !resultStatus;
    const title = hideRequiredActionsCount ? statusLabel : `${statusLabel} · 해야 할 일 ${requiredActions.length}건`;

    return (
        <div className="flex w-full flex-col gap-6">
            <ResultBanner
                resultStatus={resultStatus}
                title={title}
                description={summary ?? ""}
                onNextStepsClick={onNextStepsClick}
            />
            <div className="flex w-full flex-col gap-10">
                {visibleToolReviews.map((toolReview) => (
                    <ToolReviewCard key={toolReview.productToolReviewId} toolReview={toolReview} />
                ))}
                <SkippedToolReviews toolReviews={skippedToolReviews} />
            </div>
        </div>
    );
}

export default DiagnosisResultTab;
