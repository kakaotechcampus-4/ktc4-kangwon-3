import { useState } from "react";

import SectionIntro from "@/components/common/SectionIntro";
import MyProductList from "@/pages/Mypage/components/MyProductList.tsx";
import NotificationSettings from "@/pages/Mypage/components/NotificationSettings.tsx";
import ProductFilterBar from "@/pages/Mypage/components/ProductFilterBar.tsx";
import ProfileSection from "@/pages/Mypage/components/ProfileSection.tsx";
import RevisionNoticeBanner from "@/pages/Mypage/components/RevisionNoticeBanner/index.tsx";
import WithdrawSection from "@/pages/Mypage/components/WithdrawSection.tsx";
import { useLawAmendments } from "@/pages/Mypage/hooks/useLawAmendments.ts";
import { useMyProducts } from "@/pages/Mypage/hooks/useMyProducts.ts";

import { PAGE_SIZE } from "./constants.ts";
import type { ProductFilter } from "./types.ts";

function MyPage() {
    const [searchTerm, setSearchTerm] = useState("");
    const [filter, setFilter] = useState<ProductFilter>("all");
    const [page, setPage] = useState(0);

    const { data, isPending, isError, refetch } = useMyProducts(filter, searchTerm, page);
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

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="마이페이지" description="지금까지 진단한 상품들을 확인할 수 있어요" />
            {lawAmendments && lawAmendments.length > 0 && <RevisionNoticeBanner lawAmendments={lawAmendments} />}
            <ProfileSection />
            <NotificationSettings />
            <ProductFilterBar
                searchTerm={searchTerm}
                onSearchTermChange={handleSearchTermChange}
                filter={filter}
                onFilterChange={handleFilterChange}
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
                onProductDeleted={(wasLastOnPage) => {
                    if (wasLastOnPage && page > 0) {
                        setPage(page - 1);
                    }
                }}
            />
            <WithdrawSection />
        </div>
    );
}

export default MyPage;
