import type { SortType } from "@/api/products.ts";
import Checkbox from "@/components/common/Checkbox/index.tsx";
import { cn } from "@/lib/cn";
import { SORT_OPTIONS } from "@/pages/Products/constants.ts";

interface ProductListToolbarProps {
    selectedCount: number
    isAllSelected: boolean
    isSelectAllDisabled: boolean
    onToggleSelectAll: () => void
    onDeleteSelected: () => void
    isDeleting: boolean
    sortType: SortType
    onSortChange: (sortType: SortType) => void
}

// 목록 바로 위 한 줄. 왼쪽에서 현재 페이지 전체 선택, 오른쪽에서 정렬 기준과 선택 삭제를 다룬다.
// 불러오는 중에도 늘 렌더해서 레이아웃이 움직이지 않게 한다.
function ProductListToolbar({ selectedCount, isAllSelected, isSelectAllDisabled, onToggleSelectAll, onDeleteSelected, isDeleting, sortType, onSortChange }: ProductListToolbarProps) {
    const canDelete = selectedCount > 0 && !isDeleting;
    // 버튼 글자는 화면 크기에 따라 다르게 보이므로, 접근 이름은 aria-label로 고정한다.
    const deleteLabel = isDeleting ? "삭제 중" : selectedCount === 0 ? "선택 삭제" : `선택한 상품 ${selectedCount}개 삭제`;

    return (
        <div className="flex items-center justify-between border-t border-neutral-line pt-4">
            <div className="flex items-center gap-2">
                <Checkbox
                    checked={isAllSelected}
                    indeterminate={selectedCount > 0 && !isAllSelected}
                    disabled={isSelectAllDisabled || isDeleting}
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
            <div className="flex items-center gap-2.5 md:gap-4">
                <div role="group" aria-label="정렬" className="flex items-center gap-2.5 text-[13px] md:text-sm">
                    {SORT_OPTIONS.map(({ type, label }, index) => {
                        const selected = type === sortType;
                        return (
                            <div key={type} className="flex items-center gap-2.5">
                                {index > 0 && <span aria-hidden="true" className="h-3 w-px bg-box-line" />}
                                <button
                                    type="button"
                                    aria-pressed={selected}
                                    disabled={isDeleting}
                                    onClick={() => onSortChange(type)}
                                    className={cn(
                                        "flex cursor-pointer items-center gap-1 disabled:cursor-default",
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
                <button
                    type="button"
                    disabled={!canDelete}
                    aria-label={deleteLabel}
                    onClick={onDeleteSelected}
                    className={cn(
                        "grid place-items-center rounded-lg border px-3.5 py-1.5 text-[13px] font-bold transition-colors duration-150 outline-none md:text-sm",
                        canDelete
                            ? "cursor-pointer border-status-danger bg-status-danger text-white hover:bg-status-danger/90 focus-visible:ring-3 focus-visible:ring-status-danger/25"
                            : "cursor-default border-neutral-line bg-button-hover-bg text-button-disabled-text",
                    )}
                >
                    {/* 가장 긴 글자를 보이지 않게 같은 칸에 겹쳐 두어, 글자가 바뀌어도 버튼 너비가 변하지 않게 한다. */}
                    <span aria-hidden="true" className="invisible col-start-1 row-start-1 md:hidden">삭제 중</span>
                    <span aria-hidden="true" className="invisible col-start-1 row-start-1 hidden md:block">선택 삭제</span>
                    <span className="col-start-1 row-start-1">
                        {isDeleting ? (
                            "삭제 중"
                        ) : (
                            <>
                                <span className="md:hidden">삭제</span>
                                <span className="hidden md:inline">선택 삭제</span>
                            </>
                        )}
                    </span>
                </button>
            </div>
        </div>
    );
}

export default ProductListToolbar;
