import { Determination } from "@/api/product";
import { cn } from "@/lib/cn";

import { DETERMINATION_STYLE } from "./constants";

export type FindingFilter =
    | "all"
    | Determination.Required
    | Determination.PossiblyRequired
    | Determination.NotRequired
    | Determination.InsufficientInformation;

const FILTER_OPTIONS: { key: FindingFilter; label: string }[] = [
    { key: "all", label: "전체" },
    { key: Determination.Required, label: DETERMINATION_STYLE[Determination.Required].label },
    { key: Determination.PossiblyRequired, label: DETERMINATION_STYLE[Determination.PossiblyRequired].label },
    { key: Determination.NotRequired, label: DETERMINATION_STYLE[Determination.NotRequired].label },
    { key: Determination.InsufficientInformation, label: DETERMINATION_STYLE[Determination.InsufficientInformation].label },
];

// 선택된 필터 칩 색. 전체/정보 부족은 Mypage 필터의 중립색, 나머지는 DeterminationBadge와 같은 톤(DETERMINATION_STYLE)을 그대로 쓴다.
const FILTER_SELECTED_CLASSES: Record<FindingFilter, string> = {
    all: "text-black bg-neutral-border",
    [Determination.Required]: DETERMINATION_STYLE[Determination.Required].className,
    [Determination.PossiblyRequired]: DETERMINATION_STYLE[Determination.PossiblyRequired].className,
    [Determination.NotRequired]: DETERMINATION_STYLE[Determination.NotRequired].className,
    [Determination.InsufficientInformation]: "text-black bg-neutral-border",
};

// 선택되지 않은 칩들은 공통 스타일링을 사용한다. (Mypage ProductFilterBar와 동일한 패턴)
function filterChipClassName(key: FindingFilter, selected: boolean) {
    return cn(
        "px-3.5 py-1.5 border rounded-full text-sm font-semibold",
        selected ? FILTER_SELECTED_CLASSES[key] : "cursor-pointer text-neutral-border bg-white",
    );
}

interface FindingFilterBarProps {
    counts: Record<FindingFilter, number>
    selected: FindingFilter
    onSelect: (filter: FindingFilter) => void
}

function FindingFilterBar({ counts, selected, onSelect }: FindingFilterBarProps) {
    return (
        <div className="flex w-full flex-wrap items-center gap-2.5">
            {FILTER_OPTIONS.map(({ key, label }) => (
                <button
                    key={key}
                    type="button"
                    onClick={() => onSelect(key)}
                    className={filterChipClassName(key, key === selected)}
                >
                    {label} {counts[key]}
                </button>
            ))}
        </div>
    );
}

export default FindingFilterBar;
