import type { ProductResult } from "@/api/product";
import { ProcessingStatusType } from "@/api/types";

import { STATUS_SUMMARY_INFO } from "./statusSummaryInfo";

interface StatusSummaryBarProps {
    products: ProductResult[]
}

// 상품들을 한 번 순회하며 상태별 개수를 센다. PENDING은 BE 설명대로 IN_PROGRESS로 합친다.
// 0개인 상태도 빠지지 않도록 미리 채워둔다.
function countProductsByStatus(products: ProductResult[]): Map<ProcessingStatusType, number> {
    const counts = new Map<ProcessingStatusType, number>();
    for (const status of Object.values(ProcessingStatusType)) {
        if (status !== ProcessingStatusType.Pending) {
            counts.set(status, 0);
        }
    }

    for (const product of products) {
        const status = product.processingStatus === ProcessingStatusType.Pending
            ? ProcessingStatusType.InProgress
            : product.processingStatus;
        counts.set(status, (counts.get(status) ?? 0) + 1);
    }

    return counts;
}

function StatusSummaryBar({ products }: StatusSummaryBarProps) {
    const statusCounts = countProductsByStatus(products);

    // TODO: 컴포넌트 구성(레이아웃/스타일)은 다음 단계에서 진행. 지금은 집계한 값만 확인.
    return (
        <div>
            {Array.from(statusCounts, ([status, count]) => `${STATUS_SUMMARY_INFO[status].label} ${count}`).join(" · ")}
        </div>
    );
}

export default StatusSummaryBar;
