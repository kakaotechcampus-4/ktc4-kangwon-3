import { useState } from "react";

import { SortType } from "@/api/products.ts";
import SectionIntro from "@/components/common/SectionIntro";
import MyProductList from "@/pages/Products/components/MyProductList.tsx";
import ProductFilterBar from "@/pages/Products/components/ProductFilterBar.tsx";
import ProductListToolbar from "@/pages/Products/components/ProductListToolbar.tsx";
import RevisionNoticeBanner from "@/pages/Products/components/RevisionNoticeBanner/index.tsx";
import { PAGE_SIZE } from "@/pages/Products/constants.ts";
import { useLawAmendments } from "@/pages/Products/hooks/useLawAmendments.ts";
import { useMyProducts } from "@/pages/Products/hooks/useMyProducts.ts";
import type { ProductFilter } from "@/pages/Products/types.ts";

function ProductsPage() {
    const [searchTerm, setSearchTerm] = useState("");
    const [filter, setFilter] = useState<ProductFilter>("all");
    const [sortType, setSortType] = useState<SortType>(SortType.Latest);
    const [page, setPage] = useState(0);

    const { data, isPending, isError, refetch } = useMyProducts(filter, searchTerm, sortType, page);
    // 배너는 부가 정보라 로딩·에러일 때는 숨기고 페이지를 막지 않는다.
    const { data: lawAmendments } = useLawAmendments();

    // 렌더링 시 type error / Pagination 크래시 방지용 빈 데이터 배열과 빈 페이지 정보.
    const pagedProducts = data?.items ?? [];
    const pageInfo = data?.pageInfo ?? { page, size: PAGE_SIZE, totalElements: 0, totalPages: 1, hasNext: false };

    // 상품 검색어 / 필터가 변경되면 페이지 범위가 달라지므로 처음(0)으로 설정
    const handleSearchTermChange = (value: string) => {
        setSearchTerm(value);
        setPage(0);
    };

    const handleFilterChange = (value: ProductFilter) => {
        setFilter(value);
        setPage(0);
    };

    const handleSortChange = (value: SortType) => {
        setSortType(value);
        setPage(0);
    };

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="진단 결과" description="지금까지 진단한 상품들을 확인할 수 있어요" />
            {lawAmendments && lawAmendments.length > 0 && <RevisionNoticeBanner lawAmendments={lawAmendments} />}
            <div className="flex flex-col gap-4">
                <SectionIntro title="전체 상품" size="xl" titleAside={data ? `${pageInfo.totalElements}개` : undefined} />
                <ProductFilterBar
                    searchTerm={searchTerm}
                    onSearchTermChange={handleSearchTermChange}
                    filter={filter}
                    onFilterChange={handleFilterChange}
                />
                <ProductListToolbar sortType={sortType} onSortChange={handleSortChange} />
                <MyProductList
                    products={pagedProducts}
                    isLoading={isPending}
                    isError={isError}
                    onRetry={refetch}
                    page={page}
                    totalPages={pageInfo.totalPages}
                    hasNext={pageInfo.hasNext}
                    onPageChange={setPage}
                    onProductDeleted={(wasLastOnPage) => {
                        if (wasLastOnPage && page > 0) {
                            setPage(page - 1);
                        }
                    }}
                />
            </div>
        </div>
    );
}

export default ProductsPage;
