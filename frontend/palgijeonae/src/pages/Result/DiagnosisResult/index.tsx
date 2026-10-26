import { useState } from "react";

import { Determination, type ProductResult, ToolReviewStatus } from "@/api/product";
import { ProcessingStatusType, ResultStatus } from "@/api/types";
import { FALLBACK_BADGE, PROCESSING_STATUS_BADGES, RESULT_STATUS_BADGES } from "@/constants/statusBadges";

import FindingFilterBar, { type FindingFilter } from "./FindingFilterBar";
import ResultBanner from "./ResultBanner";
import SkippedToolReviews from "./SkippedToolReviews";
import ToolReviewCard from "./ToolReviewCard";

// 결과가 아직 없을 때 진행 상태별로 보여줄 안내 문구
const PROCESSING_STATUS_DESCRIPTIONS: Partial<Record<ProcessingStatusType, string>> = {
    [ProcessingStatusType.Pending]: "진단 대기 중이에요. 잠시만 기다려 주세요.",
    [ProcessingStatusType.InProgress]: "진단이 진행 중이에요. 완료되면 결과를 보여드릴게요.",
    [ProcessingStatusType.AwaitingInput]: "답변이 필요한 질문이 있어요. 질문에 답변해 주세요.",
    [ProcessingStatusType.Failed]: "진단에 실패했어요. 다시 시도해 주세요.",
};

interface DiagnosisResultTabProps {
    product: ProductResult
    onNextStepsClick: () => void
}

function DiagnosisResultTab({ product, onNextStepsClick }: DiagnosisResultTabProps) {
    const { resultStatus, processingStatus, summary, requiredActions, toolReviews } = product;
    const [findingFilter, setFindingFilter] = useState<FindingFilter>("all");
    const visibleToolReviews = toolReviews.filter((toolReview) => toolReview.status !== ToolReviewStatus.Skipped);
    const skippedToolReviews = toolReviews.filter((toolReview) => toolReview.status === ToolReviewStatus.Skipped);
    
    // 필터 탭에 전달한 각 Determination 상태 별 FindingCard 개수
    const allFindings = visibleToolReviews.flatMap((toolReview) => toolReview.findings);
    const findingCounts: Record<FindingFilter, number> = {
        all: allFindings.length,
        [Determination.Required]: allFindings.filter((finding) => finding.determination === Determination.Required).length,
        [Determination.PossiblyRequired]: allFindings.filter((finding) => finding.determination === Determination.PossiblyRequired).length,
        [Determination.NotRequired]: allFindings.filter((finding) => finding.determination === Determination.NotRequired).length,
        [Determination.InsufficientInformation]: allFindings.filter((finding) => finding.determination === Determination.InsufficientInformation).length,
    };

    // 결과가 아직 없으면 진행 상태(대기/진행중/입력대기/실패)별로 다른 문구를 보여준다.
    const statusLabel = resultStatus
        ? RESULT_STATUS_BADGES[resultStatus].label
        : PROCESSING_STATUS_BADGES[processingStatus]?.label ?? FALLBACK_BADGE.label;

    // 성공했거나, 진단 결과가 없을 때는 해야할 일 건수를 숨김
    const hideRequiredActionsCount = resultStatus === ResultStatus.PurchasingAgentAllowed || !resultStatus;
    const title = hideRequiredActionsCount ? statusLabel : `${statusLabel} · 해야 할 일 ${requiredActions.length}건`;
    const description = summary ?? PROCESSING_STATUS_DESCRIPTIONS[processingStatus] ?? "";

    return (
        <div className="flex w-full flex-col gap-6">
            <ResultBanner
                resultStatus={resultStatus}
                title={title}
                description={description}
                onNextStepsClick={onNextStepsClick}
            />
            <FindingFilterBar counts={findingCounts} selected={findingFilter} onSelect={setFindingFilter} />
            <div className="flex w-full flex-col gap-10">
                {visibleToolReviews.map((toolReview) => (
                    <ToolReviewCard key={toolReview.productToolReviewId} toolReview={toolReview} findingFilter={findingFilter} />
                ))}
                {skippedToolReviews.length > 0 && <hr className="w-full border-neutral-border" />}
                <SkippedToolReviews toolReviews={skippedToolReviews} />
            </div>
        </div>
    );
}

export default DiagnosisResultTab;
