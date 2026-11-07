import { Determination } from "@/api/types/product";
import { cn } from "@/lib/cn";
import { DETERMINATION_LABELS } from "@/pages/Result/components/DiagnosisResult/constants";

// 판정 결과별 배지 색
const DETERMINATION_BADGE_CLASSES: Record<Determination, string> = {
    [Determination.Required]: "text-status-danger bg-status-danger-bg border-status-danger/40",
    [Determination.PossiblyRequired]: "text-status-warning bg-status-warning-bg border-status-warning/40",
    [Determination.InsufficientInformation]: "text-neutral-muted bg-white border-box-line",
    [Determination.NotRequired]: "text-status-success bg-status-success-bg border-status-success/40",
    [Determination.NotApplicable]: "text-status-success bg-status-success-bg border-status-success/40",
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
