import { Determination } from "@/api/product";
import { cn } from "@/lib/cn";

interface DeterminationStyle {
    label: string
    className: string
}

// 판정 결과별 라벨/색
const DETERMINATION_STYLE: Record<Determination, DeterminationStyle> = {
    [Determination.Required]: { label: "필요", className: "text-status-danger bg-status-danger-bg border-status-danger" },
    [Determination.PossiblyRequired]: { label: "필요할 수 있음", className: "text-status-warning bg-status-warning-bg border-status-warning" },
    [Determination.InsufficientInformation]: { label: "정보 부족", className: "text-status-warning bg-status-warning-bg border-status-warning" },
    [Determination.NotRequired]: { label: "불필요", className: "text-status-success bg-status-success-bg border-status-success" },
    [Determination.NotApplicable]: { label: "해당 없음", className: "text-status-success bg-status-success-bg border-status-success" },
};

interface DeterminationBadgeProps {
    determination: Determination
}

function DeterminationBadge({ determination }: DeterminationBadgeProps) {
    const style = DETERMINATION_STYLE[determination];

    return (
        <div className={cn("whitespace-nowrap rounded-full border px-2.5 py-1 text-sm font-semibold", style.className)}>
            {style.label}
        </div>
    );
}

export default DeterminationBadge;
