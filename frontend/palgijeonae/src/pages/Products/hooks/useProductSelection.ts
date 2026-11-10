import { useState } from "react";

// 현재 페이지에서 고른 상품 id를 들고 있는 상태 훅.
// 검색어·필터·정렬·페이지가 바뀌면 호출하는 쪽에서 clear()로 비운다.
export function useProductSelection(pageProductIds: string[]) {
    const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());

    const isAllSelected = pageProductIds.length > 0 && pageProductIds.every((id) => selectedIds.has(id));

    const toggle = (productId: string) => {
        setSelectedIds((previous) => {
            const next = new Set(previous);
            if (!next.delete(productId)) {
                next.add(productId);
            }
            return next;
        });
    };

    // 현재 페이지가 모두 선택돼 있으면 모두 해제하고, 아니면 현재 페이지를 모두 선택한다.
    const toggleAll = () => setSelectedIds(isAllSelected ? new Set() : new Set(pageProductIds));

    const clear = () => setSelectedIds(new Set());

    return { selectedIds, isAllSelected, toggle, toggleAll, clear };
}
