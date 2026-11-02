import type { ProductResult } from "@/api/product";
import { ProcessingStatusType } from "@/api/types";
import { cn } from "@/lib/cn";

import { STATUS_SUMMARY_INFO } from "../utils/statusSummaryInfo";

interface StatusSummaryBarProps {
    products: ProductResult[]
    pollIntervalMs: number | null
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

/** Judgement 페이지 상단 요약 바. 상태별 상품 개수와 자동 갱신 주기(pollIntervalMs)를 보여준다. */
function StatusSummaryBar({ products, pollIntervalMs }: StatusSummaryBarProps) {
    const statusCounts = countProductsByStatus(products);

    return (
        <div className="flex w-full flex-wrap items-center justify-between gap-3 py-4">
            <div className="flex flex-wrap items-center gap-4.5">
                {Array.from(statusCounts, ([status, count]) => {
                    const { label, dotClassName } = STATUS_SUMMARY_INFO[status];
                    return (
                        <div key={status} className="flex items-center gap-1.5">
                            <span className={cn("size-2 rounded-full", dotClassName)} />
                            <span className="text-sm text-neutral-text">{label}</span>
                            <span className="text-sm font-bold text-black">{count}</span>
                        </div>
                    );
                })}
            </div>
            <div className="flex items-center gap-1.5">
                <span className={cn("size-2 rounded-full", pollIntervalMs != null ? "bg-status-success" : "bg-[#9d9d9d]")} />
                <span className="text-sm text-neutral-muted">
                    {pollIntervalMs != null ? `${pollIntervalMs / 1000}초마다 자동 갱신 중` : "갱신 종료"}
                </span>
            </div>
        </div>
    );
}

export default StatusSummaryBar;
