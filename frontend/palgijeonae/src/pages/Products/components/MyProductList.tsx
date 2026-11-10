import { Link, useLocation } from "react-router-dom";

import { getErrorMessage } from "@/api/core/client.ts";
import LoadingSpinner from "@/components/common/LoadingSpinner/index.tsx";
import Pagination from "@/components/common/Pagination/index.tsx";
import ProductPreview from "@/components/common/ProductPreview/index.tsx";
import SectionIntro from "@/components/common/SectionIntro/index.tsx";
import { useIsMobile } from "@/hooks/useIsMobile.ts";
import { createFromState } from "@/lib/fromState.ts";
import { PAGE_GROUP_SIZE, PAGE_GROUP_SIZE_MOBILE } from "@/pages/Mypage/constants.ts";
import { useDeleteProduct } from "@/pages/Mypage/hooks/useDeleteProduct.ts";
import type { MyProductItem } from "@/pages/Mypage/types.ts";

interface MyProductListProps {
    products: MyProductItem[]
    isLoading: boolean
    isError: boolean
    onRetry: () => void
    page: number
    totalPages: number
    hasNext: boolean
    onPageChange: (page: number) => void
    // 삭제 직전 그 상품이 현재 페이지의 마지막 하나였는지 알려준다.
    onProductDeleted: (wasLastOnPage: boolean) => void
}

function MyProductList({ products, isLoading, isError, onRetry, page, totalPages, hasNext, onPageChange, onProductDeleted }: MyProductListProps) {
    const { mutate: deleteProduct, isPending: isDeleting, variables: deletingProductId } = useDeleteProduct();
    const isMobile = useIsMobile();
    const location = useLocation();

    const handleDelete = (product: MyProductItem) => {
        const confirmed = confirm(`'${product.productName}'의 진단 결과와 첨부 이미지가 함께 삭제되고, 되돌릴 수 없어요.`);
        if (!confirmed) {
            return;
        }

        const wasLastOnPage = products.length === 1;
        deleteProduct(product.productId, {
            onSuccess: () => onProductDeleted(wasLastOnPage),
            onError: (error) => {
                alert(getErrorMessage(error, "상품을 삭제하지 못했어요. 다시 시도해주세요."));
            },
        });
    };

    return (
        <div className="flex w-full flex-col gap-6">
            <SectionIntro title="전체 상품" size="xl" />
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
                        const isDeletingThis = isDeleting && deletingProductId === product.productId;
                        return (
                            <li key={product.productId} className="relative">
                                <Link to={`/result/product/${product.productId}`} state={createFromState(location)} className="block w-full cursor-pointer">
                                    <ProductPreview
                                        productName={product.productName}
                                        productImageUrl={product.productImageUrl}
                                        resultStatus={product.resultStatus}
                                        processingStatus={product.processingStatus}
                                        sourceType={product.sourceType}
                                        hasTrailingAction
                                    />
                                </Link>
                                <button
                                    type="button"
                                    onClick={() => handleDelete(product)}
                                    disabled={isDeletingThis}
                                    aria-label={`${product.productName} 삭제`}
                                    className="absolute top-4.5 right-4 cursor-pointer rounded-full border border-box-line bg-white px-2.5 py-0.75 text-xs font-bold text-neutral-muted md:right-6 md:px-3 md:py-1 md:text-sm md:font-semibold transition-colors duration-150 outline-none hover:border-status-danger/40 hover:bg-status-danger-bg hover:text-status-danger focus-visible:border-status-danger/40 focus-visible:bg-status-danger-bg focus-visible:text-status-danger focus-visible:ring-3 focus-visible:ring-status-danger/15 disabled:cursor-default disabled:opacity-50"
                                >
                                    {isDeletingThis ? "삭제 중" : "삭제"}
                                </button>
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
