import { cn } from "@/lib/cn";

import PageNavButton from "./PageNavButton";
import { PageNavButtonType } from "./types";

interface PaginationProps {
    page: number
    totalPages: number
    hasNext: boolean
    onPageChange: (page: number) => void
    pageGroupSize?: number
}

function Pagination({ page, totalPages, hasNext, onPageChange, pageGroupSize = 10 }: PaginationProps) {
    if (totalPages <= 1) {
        return null;
    }

    // 현재 페이지가 중심에 오도록 pageGroupSize 단위 구간을 잡는다.
    const halfGroupSize = (pageGroupSize - (pageGroupSize % 2)) / 2;
    const rawStart = page - halfGroupSize;
    const maxStart = totalPages - pageGroupSize;
    const clampedStart = rawStart > maxStart ? maxStart : rawStart;
    const groupStart = clampedStart > 0 ? clampedStart : 0;
    const rawEnd = groupStart + pageGroupSize;
    const groupEnd = rawEnd < totalPages ? rawEnd : totalPages;
    const pageNumbers = Array.from({ length: groupEnd - groupStart }, (_, index) => groupStart + index);

    return (
        <div className="flex w-full items-center justify-center gap-3">
            <PageNavButton type={PageNavButtonType.First} disabled={page === 0} onClick={() => onPageChange(0)} />
            <PageNavButton type={PageNavButtonType.Prev} disabled={page === 0} onClick={() => onPageChange(page - 1)} />
            {pageNumbers.map((pageNumber) => (
                <button
                    key={pageNumber}
                    type="button"
                    onClick={() => onPageChange(pageNumber)}
                    className={cn(
                        "cursor-pointer text-sm",
                        pageNumber === page ? "font-bold text-black" : "font-medium text-neutral-border",
                    )}
                >
                    {pageNumber + 1}
                </button>
            ))}
            <PageNavButton type={PageNavButtonType.Next} disabled={!hasNext} onClick={() => onPageChange(page + 1)} />
            <PageNavButton type={PageNavButtonType.Last} disabled={!hasNext} onClick={() => onPageChange(totalPages - 1)} />
        </div>
    );
}

export default Pagination;
