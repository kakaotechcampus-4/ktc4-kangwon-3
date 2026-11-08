import { useState } from "react";

import { Determination, type Finding } from "@/api/types/product";
import lawIcon from "@/assets/result-law.svg";
import lawIconGray from "@/assets/result-law-gray.svg";
import toggleIcon from "@/assets/upload-toggle.svg";
import DefaultBox from "@/components/common/DefaultBox";
import { cn } from "@/lib/cn";

import DeterminationBadge from "./DeterminationBadge";
import LawCard from "./LawCard";
import RiskMeter from "./RiskMeter";

// 판정이 '불필요'/'해당 없음'이면 위험도를 같이 보여주지 않는다. 중복 정보이기 때문이다.
const DETERMINATIONS_WITHOUT_RISK = [Determination.NotRequired, Determination.NotApplicable];

// 근거 토글의 펼침 여부에 따른 아이콘/글자색
const EXPANDED_TOGGLE_STYLE = { icon: lawIcon, textColorClass: "text-black" };
const COLLAPSED_TOGGLE_STYLE = { icon: lawIconGray, textColorClass: "text-neutral-border" };

interface FindingCardProps {
    finding: Finding
}

function FindingCard({ finding }: FindingCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const { legalSources } = finding;
    const [firstLegalSource, ...restLegalSources] = legalSources;
    const firstLegalSourceLabel = firstLegalSource
        ? [firstLegalSource.lawName, firstLegalSource.article].filter(Boolean).join(" ") || firstLegalSource.sourceName
        : null;
    const toggleStyle = isExpanded ? EXPANDED_TOGGLE_STYLE : COLLAPSED_TOGGLE_STYLE;
    const showRiskMeter = !DETERMINATIONS_WITHOUT_RISK.includes(finding.determination);
    const legalSourcesId = `legal-sources-${finding.productFindingId}`;

    return (
        <DefaultBox>
            <div className="flex w-full flex-col gap-5.5">
                <div className="w-full overflow-hidden">
                    <div className="mb-2.5 flex shrink-0 items-center gap-2.5 md:float-right md:mb-0 md:ml-4">
                        {showRiskMeter && <RiskMeter riskLevel={finding.riskLevel} />}
                        <DeterminationBadge determination={finding.determination} />
                    </div>
                    <p className="text-lg font-bold text-black md:text-xl">{finding.subject}</p>
                </div>
                <p className="text-[15px] font-medium leading-relaxed whitespace-pre-line text-black md:text-base">{finding.summary}</p>
                <p className="text-[13px] leading-relaxed whitespace-pre-line text-neutral-text md:text-sm">{finding.rationale}</p>
            </div>
            {firstLegalSource && (
                <>
                    <button
                        type="button"
                        onClick={() => setIsExpanded((prev) => !prev)}
                        aria-expanded={isExpanded}
                        aria-controls={legalSourcesId}
                        className="flex w-full cursor-pointer flex-wrap items-center gap-2"
                    >
                        <img src={toggleStyle.icon} alt="" className="h-6 w-6" />
                        <p className={cn("text-base font-bold", toggleStyle.textColorClass)}>근거</p>
                        <p className={cn("text-sm", toggleStyle.textColorClass)}>{firstLegalSourceLabel}</p>
                        {restLegalSources.length > 0 && (
                            <p className="text-sm text-neutral-muted">외 {restLegalSources.length}건</p>
                        )}
                        <img src={toggleIcon} alt="" className={cn("h-4 w-4 transition-transform", isExpanded && "rotate-180")} />
                    </button>
                    {isExpanded && (
                        <div id={legalSourcesId} className="flex w-full flex-col gap-5">
                            {legalSources.map((legalSource) => (
                                <LawCard key={legalSource.findingLegalSourceId} legalSource={legalSource} />
                            ))}
                        </div>
                    )}
                </>
            )}
        </DefaultBox>
    );
}

export default FindingCard;
