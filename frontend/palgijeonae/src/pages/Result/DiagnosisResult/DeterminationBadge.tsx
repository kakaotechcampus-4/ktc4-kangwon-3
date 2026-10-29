import { Determination } from "@/api/product";
import { cn } from "@/lib/cn";

import { DETERMINATION_LABELS } from "./constants";

// 판정 결과별 배지 색
const DETERMINATION_BADGE_CLASSES: Record<Determination, string> = {
    [Determination.Required]: "text-status-danger bg-status-danger-bg border-status-danger",
    [Determination.PossiblyRequired]: "text-status-warning bg-status-warning-bg border-status-warning",
    [Determination.InsufficientInformation]: "text-neutral-dark bg-white border-neutral-border",
    [Determination.NotRequired]: "text-status-success bg-status-success-bg border-status-success",
    [Determination.NotApplicable]: "text-status-success bg-status-success-bg border-status-success",
};

interface DeterminationBadgeProps {
    determination: Determination
}

function DeterminationBadge({ determination }: DeterminationBadgeProps) {
    return (
        <div className={cn("whitespace-nowrap rounded-full border px-2.5 py-1 text-sm font-semibold", DETERMINATION_BADGE_CLASSES[determination])}>
            {DETERMINATION_LABELS[determination]}
        </div>
    );
}

export default DeterminationBadge;
