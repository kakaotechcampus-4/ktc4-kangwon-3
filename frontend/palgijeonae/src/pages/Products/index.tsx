import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { getErrorMessage } from "@/api/core/client.ts";
import SectionIntro from "@/components/common/SectionIntro";
import MyProductList from "@/pages/Products/components/MyProductList.tsx";
import ProductFilterBar from "@/pages/Products/components/ProductFilterBar.tsx";
import ProductListToolbar from "@/pages/Products/components/ProductListToolbar.tsx";
import RevisionNoticeBanner from "@/pages/Products/components/RevisionNoticeBanner/index.tsx";
import { PAGE_SIZE } from "@/pages/Products/constants.ts";
import { useDeleteProducts } from "@/pages/Products/hooks/useDeleteProducts.ts";
import { useLawAmendments } from "@/pages/Products/hooks/useLawAmendments.ts";
import { useMyProducts } from "@/pages/Products/hooks/useMyProducts.ts";
import { useProductListParams } from "@/pages/Products/hooks/useProductListParams.ts";
import { useProductSelection } from "@/pages/Products/hooks/useProductSelection.ts";
import { getLastPageIndex } from "@/pages/Products/utils/listParams.ts";

function ProductsPage() {
    const { filter, keyword, sortType, page, setFilter, setKeyword, setSortType, setPage, replacePage } = useProductListParams();
    const { search } = useLocation();

    const { data, isPending, isError, refetch } = useMyProducts(filter, keyword, sortType, page);
    // 배너는 부가 정보라 로딩·에러일 때는 숨기고 페이지를 막지 않는다.
    const { data: lawAmendments } = useLawAmendments();

    // 렌더링 시 type error / Pagination 크래시 방지용 빈 데이터 배열과 빈 페이지 정보.
    const pagedProducts = data?.items ?? [];
    const pageInfo = data?.pageInfo ?? { page, size: PAGE_SIZE, totalElements: 0, totalPages: 1, hasNext: false };

    // 조건이 바뀌어 주소가 달라지면 보이지 않게 된 선택을 비운다. (뒤로 가기, 없는 페이지 보정도 포함)
    const { selectedIds, isAllSelected, toggle, toggleAll, retain } = useProductSelection(
        pagedProducts.map((product) => product.productId),
        search,
    );
    const { mutate: deleteProducts, isPending: isDeleting } = useDeleteProducts();

    // 주소의 페이지가 마지막 페이지를 넘으면(직접 입력, 마지막 페이지 상품을 모두 삭제) 마지막 페이지로 주소를 고친다.
    useEffect(() => {
        if (!data) {
            return;
        }
        const lastPage = getLastPageIndex(data.pageInfo.totalPages);
        if (page > lastPage) {
            replacePage(lastPage);
        }
    }, [data, page, replacePage]);

    const handleDeleteSelected = () => {
        const productIds = Array.from(selectedIds);
        const confirmed = confirm(`선택한 상품 ${productIds.length}개의 진단 결과와 첨부 이미지가 함께 삭제되고, 되돌릴 수 없어요.`);
        if (!confirmed) {
            return;
        }

        deleteProducts(productIds, {
            onSuccess: ({ failedIds, firstError }) => {
                retain(failedIds);
                if (failedIds.length > 0) {
                    alert(`${productIds.length}개 중 ${failedIds.length}개를 삭제하지 못했어요.\n${getErrorMessage(firstError, "다시 시도해주세요.")}`);
                }
            },
        });
    };

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="진단 결과" description="지금까지 진단한 상품들을 확인할 수 있어요" />
            {lawAmendments && lawAmendments.length > 0 && <RevisionNoticeBanner lawAmendments={lawAmendments} />}
            <div className="flex flex-col gap-4">
                <SectionIntro title="전체 상품" size="xl" titleAside={data ? `${pageInfo.totalElements}개` : undefined} />
                <ProductFilterBar
                    searchTerm={keyword}
                    onSearchTermChange={setKeyword}
                    filter={filter}
                    onFilterChange={setFilter}
                />
                <ProductListToolbar
                    selectedCount={selectedIds.size}
                    isAllSelected={isAllSelected}
                    isSelectAllDisabled={isPending || isError || pagedProducts.length === 0}
                    onToggleSelectAll={toggleAll}
                    onDeleteSelected={handleDeleteSelected}
                    isDeleting={isDeleting}
                    sortType={sortType}
                    onSortChange={setSortType}
                />
                <MyProductList
                    products={pagedProducts}
                    isLoading={isPending}
                    isError={isError}
                    onRetry={refetch}
                    page={page}
                    totalPages={pageInfo.totalPages}
                    hasNext={pageInfo.hasNext}
                    onPageChange={setPage}
                    selectedIds={selectedIds}
                    onToggleSelect={toggle}
                    isSelectionDisabled={isDeleting}
                />
            </div>
        </div>
    );
}

export default ProductsPage;
