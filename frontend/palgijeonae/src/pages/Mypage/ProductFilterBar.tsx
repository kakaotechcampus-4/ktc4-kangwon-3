import { cva } from "class-variance-authority";
import { type FormEvent, useState } from "react";

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
    // 타이핑 중인 값과 실제로 검색을 실행할 값을 분리한다 — 한 글자씩 바뀔 때마다 조회하면 안 되고,
    // Enter나 검색 버튼을 눌렀을 때만(=commitSearch) 부모에 알려서 조회가 나가야 한다.
    const [draftSearchTerm, setDraftSearchTerm] = useState(searchTerm);

    const handleSubmit = (event: FormEvent) => {
        event.preventDefault();
        onSearchTermChange(draftSearchTerm);
    };

    return (
        <div className="px-1.5 flex flex-col gap-3">
            <form onSubmit={handleSubmit} className="relative w-full">
                <input
                    type="text"
                    placeholder="상품명으로 검색하세요"
                    value={draftSearchTerm}
                    onChange={(event) => setDraftSearchTerm(event.target.value)}
                    className="w-full rounded-full border border-neutral-border px-5 py-3 pr-12"
                />
                <button
                    type="submit"
                    className="absolute right-4 top-1/2 h-6 w-6 -translate-y-1/2 cursor-pointer"
                >
                    <img src={search} alt="검색" className="h-full w-full" />
                </button>
            </form>
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
