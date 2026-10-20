import type { ProductResult } from "@/api/product";
import { ResultStatus } from "@/api/types";
import { RESULT_STATUS_BADGES } from "@/constants/statusBadges";

import ResultBanner from "./ResultBanner";
import ToolReviewCard from "./ToolReviewCard";

interface DiagnosisResultTabProps {
    product: ProductResult
    onNextStepsClick: () => void
}

function DiagnosisResultTab({ product, onNextStepsClick }: DiagnosisResultTabProps) {
    const { resultStatus, summary, requiredActions, toolReviews } = product;
    const isSuccess = resultStatus === ResultStatus.PurchasingAgentAllowed;

    return (
        <div className="flex w-full flex-col gap-6">
            {resultStatus && (
                <ResultBanner
                    resultStatus={resultStatus}
                    title={
                        isSuccess
                            ? RESULT_STATUS_BADGES[resultStatus].label
                            : `${RESULT_STATUS_BADGES[resultStatus].label} · 해야 할 일 ${requiredActions.length}건`
                    }
                    description={summary ?? ""}
                    onNextStepsClick={onNextStepsClick}
                />
            )}
            {toolReviews.map((toolReview) => (
                <ToolReviewCard key={toolReview.productToolReviewId} toolReview={toolReview} />
            ))}
        </div>
    );
}

export default DiagnosisResultTab;
