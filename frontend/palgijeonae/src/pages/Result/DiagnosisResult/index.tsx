import { useId, useState } from "react";

import type { Finding, ProductResult } from "@/api/product";
import { ToolReviewStatus } from "@/api/product";

import { DETERMINATION_DESCRIPTIONS, DETERMINATION_LABELS, DETERMINATION_LEGEND_ORDER } from "./constants";
import FindingFilterBar, { type FindingFilter } from "./FindingFilterBar";
import ResultBanner from "./ResultBanner";
import SkippedToolReviews from "./SkippedToolReviews";
import ToolReviewCard from "./ToolReviewCard";

interface DiagnosisResultTabProps {
    product: ProductResult
    diagnosesId?: string
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

function DiagnosisResultTab({ product, diagnosesId, onNextStepsClick }: DiagnosisResultTabProps) {
    const { toolReviews } = product;
    
    // productId로 접근해 diagnosesId가 없는 경우 경로를 만들지 않는다.
    const judgementPath = diagnosesId ? `/judgement/${diagnosesId}` : undefined;
    // question은 product 단위로만 접근 가능하다
    const questionPath = `/question/${product.productId}`;

    const [findingFilter, setFindingFilter] = useState<FindingFilter>(null);

    const determinationTooltipId = useId();

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
                    <div className="group relative shrink-0">
                        <button
                            type="button"
                            aria-label="판정·위험도 설명"
                            aria-describedby={determinationTooltipId}
                            className="flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-neutral-border text-xs leading-none font-medium text-neutral-border"
                        >
                            ?
                        </button>
                        <div
                            id={determinationTooltipId}
                            role="tooltip"
                            className="pointer-events-none absolute right-0 bottom-full z-50 mb-2 hidden w-max flex-col gap-1 whitespace-nowrap rounded-lg bg-neutral-dark px-4 py-3 text-sm text-white shadow-lg group-hover:flex group-focus-within:flex"
                        >
                            {DETERMINATION_LEGEND_ORDER.map((determination) => (
                                <p key={determination}>
                                    <span className="font-semibold">{DETERMINATION_LABELS[determination]}</span>
                                    {" · "}
                                    {DETERMINATION_DESCRIPTIONS[determination]}
                                </p>
                            ))}
                            <p className="mt-1 text-white/70">위험도는 문제가 생겼을 때 심각성이 얼마나 큰지를 나타내요.</p>
                        </div>
                    </div>
                )}
            </div>
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
