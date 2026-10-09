import Pagination from "@/components/common/Pagination/index.tsx";
import SectionIntro from "@/components/common/SectionIntro/index.tsx";

import { PAGE_GROUP_SIZE } from "./constraints.ts";
import MyProduct from "./MyProduct.tsx";
import type { MyProductItem } from "./types.ts";

interface MyProductListProps {
    products: MyProductItem[]
    isLoading: boolean
    isError: boolean
    onRetry: () => void
    page: number
    totalPages: number
    hasNext: boolean
    onPageChange: (page: number) => void
}

function MyProductList({ products, isLoading, isError, onRetry, page, totalPages, hasNext, onPageChange }: MyProductListProps) {
    return (
        <div className="flex w-full flex-col gap-6">
            <SectionIntro title="전체 상품" size="xl" />
            {isLoading ? (
                <div className="flex w-full justify-center py-12">
                    <div className="h-10 w-10 animate-spin rounded-full border-4 border-neutral-border border-t-white" />
                </div>
            ) : isError ? (
                <div className="flex w-full flex-col items-center gap-3 py-12">
                    <p className="text-sm font-medium text-status-danger">상품 목록을 불러오지 못했어요.</p>
                    <button
                        type="button"
                        onClick={onRetry}
                        className="text-sm font-medium cursor-pointer text-neutral-border underline underline-offset-2"
                    >
                        다시 시도
                    </button>
                </div>
            ) : products.length === 0 ? (
                <p className="w-full py-12 text-center text-sm font-medium text-neutral-border">
                    조건에 맞는 상품이 없어요.
                </p>
            ) : (
                <div className="flex w-full flex-col gap-3.5">
                    {products.map((product) => (
                        <MyProduct key={product.productId} {...product} />
                    ))}
                </div>
            )}
            <Pagination page={page} totalPages={totalPages} hasNext={hasNext} onPageChange={onPageChange} pageGroupSize={PAGE_GROUP_SIZE} />
        </div>
    );
}

export default MyProductList;
