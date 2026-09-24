import lastPageIcon from "@/assets/mypage-last-page.svg";
import nextPageIcon from "@/assets/mypage-next-page.svg";
import SectionIntro from "@/components/common/SectionIntro/index.tsx";
import { cn } from "@/lib/cn";

import MyProduct from "./MyProduct.tsx";
import type { MyProductItem } from "./types.ts";

interface MyProductListProps {
    products: MyProductItem[]
    page: number
    totalPages: number
    onPageChange: (page: number) => void
}

const PAGE_GROUP_SIZE = 10;

function MyProductList({ products, page, totalPages, onPageChange }: MyProductListProps) {
    const groupStart = Math.floor(page / PAGE_GROUP_SIZE) * PAGE_GROUP_SIZE;
    const groupEnd = Math.min(groupStart + PAGE_GROUP_SIZE, totalPages);
    const pageNumbers = Array.from({ length: groupEnd - groupStart }, (_, index) => groupStart + index);

    return (
        <div className="flex w-full flex-col gap-6">
            <SectionIntro title="전체 상품" size="xl" />
            <div className="flex w-full flex-col gap-3.5">
                {products.map((product) => (
                    <MyProduct key={product.productId} {...product} />
                ))}
            </div>
            {totalPages > 1 && (
                <div className="flex w-full items-center justify-center gap-3">
                    <button type="button" disabled={page === 0} onClick={() => onPageChange(0)} className="cursor-pointer disabled:cursor-default disabled:opacity-30">
                        <img src={lastPageIcon} alt="처음" className="h-4 w-4 -scale-x-100" />
                    </button>
                    <button type="button" disabled={page === 0} onClick={() => onPageChange(page - 1)} className="cursor-pointer disabled:cursor-default disabled:opacity-30">
                        <img src={nextPageIcon} alt="이전" className="h-4 w-4 -scale-x-100" />
                    </button>
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
                    <button type="button" disabled={page === totalPages - 1} onClick={() => onPageChange(page + 1)} className="cursor-pointer disabled:cursor-default disabled:opacity-30">
                        <img src={nextPageIcon} alt="다음" className="h-4 w-4" />
                    </button>
                    <button type="button" disabled={page === totalPages - 1} onClick={() => onPageChange(totalPages - 1)} className="cursor-pointer disabled:cursor-default disabled:opacity-30">
                        <img src={lastPageIcon} alt="마지막 페이지" className="h-4 w-4" />
                    </button>
                </div>
            )}
        </div>
    );
}

export default MyProductList;
