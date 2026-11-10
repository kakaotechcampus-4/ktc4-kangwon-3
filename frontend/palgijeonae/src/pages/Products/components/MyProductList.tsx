import { Link, useLocation } from "react-router-dom";

import Checkbox from "@/components/common/Checkbox/index.tsx";
import LoadingSpinner from "@/components/common/LoadingSpinner/index.tsx";
import Pagination from "@/components/common/Pagination/index.tsx";
import ProductPreview from "@/components/common/ProductPreview/index.tsx";
import { useIsMobile } from "@/hooks/useIsMobile.ts";
import { createFromState } from "@/lib/fromState.ts";
import { PAGE_GROUP_SIZE, PAGE_GROUP_SIZE_MOBILE } from "@/pages/Products/constants.ts";
import type { MyProductItem } from "@/pages/Products/types.ts";

interface MyProductListProps {
    products: MyProductItem[]
    isLoading: boolean
    isError: boolean
    onRetry: () => void
    page: number
    totalPages: number
    hasNext: boolean
    onPageChange: (page: number) => void
    selectedIds: ReadonlySet<string>
    onToggleSelect: (productId: string) => void
    // 삭제 요청이 진행 중일 때 선택을 바꾸지 못하게 한다.
    isSelectionDisabled: boolean
}

function MyProductList({ products, isLoading, isError, onRetry, page, totalPages, hasNext, onPageChange, selectedIds, onToggleSelect, isSelectionDisabled }: MyProductListProps) {
    const isMobile = useIsMobile();
    const location = useLocation();

    return (
        <div className="flex w-full flex-col gap-6">
            {isLoading ? (
                <LoadingSpinner />
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
                <ul aria-label="전체 상품" className="flex w-full flex-col gap-3.5">
                    {products.map((product) => {
                        return (
                            <li key={product.productId} className="flex items-center gap-3 md:gap-4">
                                <Checkbox
                                    checked={selectedIds.has(product.productId)}
                                    disabled={isSelectionDisabled}
                                    onChange={() => onToggleSelect(product.productId)}
                                    ariaLabel={`${product.productName} 선택`}
                                />
                                <Link to={`/result/product/${product.productId}`} state={createFromState(location)} className="block min-w-0 flex-1 cursor-pointer">
                                    <ProductPreview
                                        productName={product.productName}
                                        productImageUrl={product.productImageUrl}
                                        resultStatus={product.resultStatus}
                                        processingStatus={product.processingStatus}
                                        sourceType={product.sourceType}
                                        selected={selectedIds.has(product.productId)}
                                    />
                                </Link>
                            </li>
                        );
                    })}
                </ul>
            )}
            <Pagination page={page} totalPages={totalPages} hasNext={hasNext} onPageChange={onPageChange} pageGroupSize={isMobile ? PAGE_GROUP_SIZE_MOBILE : PAGE_GROUP_SIZE} />
        </div>
    );
}

export default MyProductList;
