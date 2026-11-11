import { useState } from "react";

// 현재 페이지에서 고른 상품 id를 들고 있는 상태 훅.
// resetKey(예: 주소의 쿼리)가 바뀌면 고른 상품을 비운다. 조건이 바뀌어 목록이 달라졌기 때문이다.
export function useProductSelection(pageProductIds: string[], resetKey: string) {
    const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());
    const [syncedResetKey, setSyncedResetKey] = useState(resetKey);
    if (resetKey !== syncedResetKey) {
        setSyncedResetKey(resetKey);
        setSelectedIds(new Set());
    }

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

    // 삭제에 실패한 상품처럼 주어진 id만 선택으로 남긴다.
    const retain = (productIds: string[]) => setSelectedIds(new Set(productIds));

    return { selectedIds, isAllSelected, toggle, toggleAll, retain };
}
