import { useState } from "react";

import type { Finding, ProductResult } from "@/api/types/product";
import { ToolReviewStatus } from "@/api/types/product";
import HelpTooltip from "@/components/common/HelpTooltip";
import FindingFilterBar from "@/pages/Result/components/DiagnosisResult/components/FindingFilterBar";
import ResultBanner from "@/pages/Result/components/DiagnosisResult/components/ResultBanner";
import SkippedToolReviews from "@/pages/Result/components/DiagnosisResult/components/SkippedToolReviews";
import ToolReviewCard from "@/pages/Result/components/DiagnosisResult/components/ToolReviewCard";

import { DETERMINATION_DESCRIPTIONS, DETERMINATION_LABELS, DETERMINATION_LEGEND_ORDER } from "./constants";
import type { FindingFilter } from "./types";

interface DiagnosisResultTabProps {
    product: ProductResult
    onNextStepsClick: () => void
}

// 필터 탭에 전달할 각 Determination 상태 별 FindingCard 개수. null은 "전체"를 나타낸다.
function countFindingsByDetermination(findings: Finding[]): Map<FindingFilter, number> {
    const counts = new Map<FindingFilter, number>([[null, findings.length]]);
    for (const determination of DETERMINATION_LEGEND_ORDER) {
        counts.set(determination, findings.filter((finding) => finding.determination === determination).length);
    }
    return counts;
}

function DiagnosisResultTab({ product, onNextStepsClick }: DiagnosisResultTabProps) {
    const { toolReviews } = product;

    const judgementPath = `/judgement/${product.diagnosesId}`;
    // question은 product 단위로만 접근 가능하다
    const questionPath = `/question/${product.productId}`;

    const [findingFilter, setFindingFilter] = useState<FindingFilter>(null);

    const visibleToolReviews = toolReviews.filter((toolReview) => toolReview.status !== ToolReviewStatus.Skipped);
    const skippedToolReviews = toolReviews.filter((toolReview) => toolReview.status === ToolReviewStatus.Skipped);

    const allFindings = visibleToolReviews.flatMap((toolReview) => toolReview.findings);
    const findingCounts = countFindingsByDetermination(allFindings);

    return (
        <div className="flex w-full flex-col gap-6">
            <ResultBanner
                product={product}
                judgementPath={judgementPath}
                questionPath={questionPath}
                onNextStepsClick={onNextStepsClick}
            />
            <div className="flex w-full flex-wrap items-center justify-between gap-2.5">
                <FindingFilterBar counts={findingCounts} selected={findingFilter} onSelect={setFindingFilter} />
                {allFindings.length > 0 && (
                    <HelpTooltip label="판정·위험도 설명" className="max-w-none whitespace-nowrap">
                        {DETERMINATION_LEGEND_ORDER.map((determination) => (
                            <p key={determination}>
                                <span className="font-semibold">{DETERMINATION_LABELS[determination]}</span>
                                {" · "}
                                {DETERMINATION_DESCRIPTIONS[determination]}
                            </p>
                        ))}
                        <p className="mt-1 text-white/70">위험도는 문제가 생겼을 때 심각성이 얼마나 큰지를 나타내요.</p>
                    </HelpTooltip>
                )}
            </div>
            <div className="flex w-full flex-col gap-15">
                {visibleToolReviews.map((toolReview) => (
                    <ToolReviewCard key={toolReview.productToolReviewId} toolReview={toolReview} findingFilter={findingFilter} />
                ))}
                {skippedToolReviews.length > 0 && <hr className="w-full border-neutral-line" />}
                <SkippedToolReviews toolReviews={skippedToolReviews} />
            </div>
        </div>
    );
}

export default DiagnosisResultTab;
