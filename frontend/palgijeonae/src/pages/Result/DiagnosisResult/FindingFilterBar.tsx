import { Determination } from "@/api/product";
import { cn } from "@/lib/cn";

import { DETERMINATION_LABELS } from "./constants";

// null은 "전체"(필터 없음)를 의미한다.
export type FindingFilter = Determination | null;

const FILTER_OPTIONS: { key: FindingFilter; label: string }[] = [
    { key: null, label: "전체" },
    { key: Determination.Required, label: DETERMINATION_LABELS[Determination.Required] },
    { key: Determination.PossiblyRequired, label: DETERMINATION_LABELS[Determination.PossiblyRequired] },
    { key: Determination.NotRequired, label: DETERMINATION_LABELS[Determination.NotRequired] },
    { key: Determination.InsufficientInformation, label: DETERMINATION_LABELS[Determination.InsufficientInformation] },
];

// 선택된 필터 칩 색. 매핑에 없는 판정(정보 부족 등)과 "전체"는 중립색으로 통일한다.
const NEUTRAL_SELECTED_CLASSES = "text-black bg-neutral-border";
const FILTER_SELECTED_CLASSES: Partial<Record<Determination, string>> = {
    [Determination.Required]: "text-status-danger bg-status-danger-bg border-status-danger",
    [Determination.PossiblyRequired]: "text-status-warning bg-status-warning-bg border-status-warning",
    [Determination.NotRequired]: "text-status-success bg-status-success-bg border-status-success",
};

// 선택되지 않은 칩들은 공통 스타일링 사용.
function filterChipClassName(key: FindingFilter, selected: boolean) {
    const selectedClassName = key !== null ? FILTER_SELECTED_CLASSES[key] : undefined;
    return cn(
        "px-3.5 py-1.5 border rounded-full text-sm font-semibold",
        selected ? selectedClassName ?? NEUTRAL_SELECTED_CLASSES : "cursor-pointer text-neutral-border bg-white",
    );
}

interface FindingFilterBarProps {
    counts: Map<FindingFilter, number>
    selected: FindingFilter
    onSelect: (filter: FindingFilter) => void
}

function FindingFilterBar({ counts, selected, onSelect }: FindingFilterBarProps) {
    return (
        <div className="flex w-full flex-wrap items-center gap-2.5">
            {FILTER_OPTIONS.map(({ key, label }) => (
                <button
                    key={key ?? "all"}
                    type="button"
                    onClick={() => onSelect(key)}
                    className={filterChipClassName(key, key === selected)}
                >
                    {label} {counts.get(key) ?? 0}
                </button>
            ))}
        </div>
    );
}

export default FindingFilterBar;
