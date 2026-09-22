import { cva } from "class-variance-authority";

import search from "@/assets/mypage-search.svg"

import type { ProductFilter } from "./types.ts";

const FILTER_TABS: { key: ProductFilter; label: string }[] = [
    { key: "all", label: "전체" },
    { key: "PURCHASING_AGENT_ALLOWED", label: "구매 대행 가능" },
    { key: "DIRECT_IMPORT_CERTIFICATION_REQUIRED", label: "사입 인증 필요" },
    { key: "RECHECK_REQUIRED", label: "재확인 필요" },
];

const filterTabVariants = cva("px-3.5 py-1.5 border rounded-full text-sm font-semibold", {
    variants: {
        tone: {
            all: "",
            PURCHASING_AGENT_ALLOWED: "",
            DIRECT_IMPORT_CERTIFICATION_REQUIRED: "",
            RECHECK_REQUIRED: "",
        },
        selected: {
            true: "",
            false: "cursor-pointer text-neutral-border bg-white",
        },
    },
    // 선택됐을 때만 tone별로 다른 색을 얹는다.
    compoundVariants: [
        { tone: "all", selected: true, className: "text-black bg-neutral-border" },
        { tone: "PURCHASING_AGENT_ALLOWED", selected: true, className: "text-status-success bg-status-success-bg" },
        { tone: "DIRECT_IMPORT_CERTIFICATION_REQUIRED", selected: true, className: "text-status-danger bg-status-danger-bg" },
        { tone: "RECHECK_REQUIRED", selected: true, className: "text-status-warning bg-status-warning-bg" },
    ],
});

interface ProductFilterBarProps {
    searchTerm: string
    onSearchTermChange: (value: string) => void
    filter: ProductFilter
    onFilterChange: (filter: ProductFilter) => void
}

function ProductFilterBar({ searchTerm, onSearchTermChange, filter, onFilterChange }: ProductFilterBarProps) {
    return (
        <div className="px-1.5 flex flex-col gap-3">
            <div className="relative w-full">
                <input
                    type="text"
                    placeholder="상품명으로 검색하세요"
                    value={searchTerm}
                    onChange={(event) => onSearchTermChange(event.target.value)}
                    className="w-full rounded-full border border-neutral-border px-5 py-3 pr-12"
                />
                <button
                    type="button"
                    // TODO: 지금은 onChange로 이미 실시간 필터링되고 있어서 자리만 잡아둠. 실제 검색 트리거가 필요하면 여기에 채워넣기.
                    onClick={() => {}}
                    className="absolute right-4 top-1/2 h-6 w-6 -translate-y-1/2 cursor-pointer"
                >
                    <img src={search} alt="검색" className="h-full w-full" />
                </button>
            </div>
            <div className="flex w-full items-center gap-2">
                {FILTER_TABS.map(({ key, label }) => (
                    <button
                        key={key}
                        type="button"
                        onClick={() => onFilterChange(key)}
                        className={filterTabVariants({ tone: key, selected: filter === key })}
                    >
                        {label}
                    </button>
                ))}
            </div>
        </div>
    );
}

export default ProductFilterBar;
