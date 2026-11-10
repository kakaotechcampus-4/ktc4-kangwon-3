import type { SortType } from "@/api/products.ts";
import Checkbox from "@/components/common/Checkbox/index.tsx";
import { cn } from "@/lib/cn";
import { SORT_OPTIONS } from "@/pages/Products/constants.ts";

interface ProductListToolbarProps {
    selectedCount: number
    isAllSelected: boolean
    isSelectAllDisabled: boolean
    onToggleSelectAll: () => void
    sortType: SortType
    onSortChange: (sortType: SortType) => void
}

// 목록 바로 위 한 줄. 왼쪽에서 현재 페이지 전체 선택, 오른쪽에서 정렬 기준을 고른다.
// 불러오는 중에도 늘 렌더해서 레이아웃이 움직이지 않게 한다.
function ProductListToolbar({ selectedCount, isAllSelected, isSelectAllDisabled, onToggleSelectAll, sortType, onSortChange }: ProductListToolbarProps) {
    return (
        <div className="flex items-center justify-between border-t border-neutral-line pt-4">
            <div className="flex items-center gap-2">
                <Checkbox
                    checked={isAllSelected}
                    indeterminate={selectedCount > 0 && !isAllSelected}
                    disabled={isSelectAllDisabled}
                    onChange={onToggleSelectAll}
                    ariaLabel="현재 페이지 전체 선택"
                />
                <span className="text-sm font-bold text-neutral-text md:text-[15px]">
                    {selectedCount === 0 ? "전체 선택" : (
                        <>
                            <span className="text-primary">{selectedCount}개</span> 선택됨
                        </>
                    )}
                </span>
            </div>
            <div role="group" aria-label="정렬" className="flex items-center gap-2.5 text-[13px] md:text-sm">
                {SORT_OPTIONS.map(({ type, label }, index) => {
                    const selected = type === sortType;
                    return (
                        <div key={type} className="flex items-center gap-2.5">
                            {index > 0 && <span aria-hidden="true" className="h-3 w-px bg-box-line" />}
                            <button
                                type="button"
                                aria-pressed={selected}
                                onClick={() => onSortChange(type)}
                                className={cn(
                                    "flex cursor-pointer items-center gap-1",
                                    selected ? "font-bold text-neutral-text" : "font-medium text-neutral-border",
                                )}
                            >
                                {selected && (
                                    <svg aria-hidden="true" viewBox="0 0 16 16" fill="none" className="size-4 text-primary">
                                        <path d="M3.5 8.5l3 3 6-6.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                                    </svg>
                                )}
                                {label}
                            </button>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export default ProductListToolbar;
